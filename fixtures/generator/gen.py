"""Seeded generator for the synthetic fixture corpus.

    python fixtures/generator/gen.py

Rewrites fixtures/synthetic/, fixtures/expected/, fixtures/pii/ and
fixtures/manifest.json. Output is byte-identical for the same seed.json on any
OS and Python >= 3.12: only random.Random(seed).random/randrange/choice are
used, files are written as bytes, and nothing iterates over a set.

Export shapes follow docs/LLD.md and public parser docs; they are NOT copied
from real exports. TODO(fixture-real): replace or cross-check against ~30 real
anonymized exports (see fixtures/README.md for each assumption).
"""

from __future__ import annotations

import json
import random
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import content  # noqa: E402
import pii  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SYNTH = ROOT / "synthetic"
EXPECTED = ROOT / "expected"

NNBSP = " "  # narrow no-break space before AM/PM
LRM = "‎"  # left-to-right mark before iOS attachment/system lines
ENCRYPTION_NOTICE = (
    "Messages and calls are end-to-end encrypted. Only people in this chat can read, listen to, or share them."
)
MINUTE_MS = 60_000
DAY_MS = 86_400_000


# ---------------------------------------------------------------- time zones


@dataclass(frozen=True)
class Zone:
    """Offsets as the JS-built transition table describes them (LLD: Time zones)."""

    name: str
    # (utc_ms at which the offset starts, offset minutes east of UTC), ascending
    rules: tuple[tuple[int, int], ...]

    def offset_at_utc(self, utc_ms: int) -> int:
        offset = self.rules[0][1]
        for start, off in self.rules:
            if utc_ms >= start:
                offset = off
        return offset

    def transitions(self) -> list[dict[str, int]]:
        # from_local_min = the local wall-clock minute (read as if UTC) where the new offset begins.
        return [{"from_local_min": start // MINUTE_MS + off, "offset_min": off} for start, off in self.rules]

    def is_ambiguous_local(self, local_ms: int) -> bool:
        """True inside a fall-back overlap, where a wall-clock time maps to two instants."""
        for (_, before), (start, after) in zip(self.rules, self.rules[1:], strict=False):
            # Clocks go back at `start`: local times [start+after, start+before) are read twice.
            if after < before and start + after * MINUTE_MS <= local_ms < start + before * MINUTE_MS:
                return True
        return False


def utc_ms(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp() * 1000)


KOLKATA = Zone("Asia/Kolkata", ((utc_ms(1970, 1, 1), 330),))
# BST ends 2026-10-25 01:00 UTC; the local hour 01:00-02:00 occurs twice and is kept message-free.
LONDON = Zone("Europe/London", ((utc_ms(1970, 1, 1), 60), (utc_ms(2026, 10, 25, 1), 0)))


# -------------------------------------------------------------- conversation


@dataclass
class Message:
    utc_ms: int
    sender: int  # index into Chat.names; -1 = system
    kind: str  # Text | Media | Sticker | Deleted | System | Link
    text: str
    edited: bool = False
    special: bool = False  # carries a canary/PII line; renderers must keep its text
    reactions: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class Chat:
    names: list[str]
    messages: list[Message]


def pick_line(rng: random.Random, hinglish_p: float, intent: str) -> str:
    pool = content.HINGLISH if rng.random() < hinglish_p else content.ENGLISH
    line: str = rng.choice(pool[intent])
    if intent in ("plain", "answer", "affection") and rng.random() < 0.15:
        line += " " + rng.choice(content.EMOJIS)
    return line


INTENTS = ["plain"] * 6 + ["question"] * 3 + ["answer"] * 3 + ["laugh"] * 2 + ["filler"] * 2 + [
    "affection",
    "we",
    "conflict",
]
SESSION_HOURS = [8, 9, 12, 13, 17, 19, 20, 21, 21, 22, 22, 23, 23, 0, 1, 2]


def make_chat(
    rng: random.Random,
    names: list[str],
    zone: Zone,
    start_local: datetime,
    days: int,
    hinglish_p: float,
    special_lines: list[str],
) -> Chat:
    """Sessions of alternating turns. SELF (index 0) initiates ~70% of sessions, since the user chases."""
    messages: list[Message] = []
    last_end = 0
    for day in range(days):
        day_local = int(start_local.replace(tzinfo=UTC).timestamp() * 1000) + day * DAY_MS
        for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
            local = day_local + rng.choice(SESSION_HOURS) * 3_600_000 + rng.randrange(3_600_000)
            t = local - zone.offset_at_utc(local - zone.rules[-1][1] * MINUTE_MS) * MINUTE_MS
            t = max(t, last_end + 5 * MINUTE_MS)
            speaker = 0 if rng.random() < 0.7 else 1
            if len(names) > 2:
                speaker = rng.randrange(len(names))
            for _turn in range(rng.choice([2, 3, 3, 4, 5, 6])):
                for _msg in range(rng.choice([1, 1, 2, 3] if speaker == 0 else [1, 1, 1, 2])):
                    messages.append(Message(t, speaker, "Text", pick_line(rng, hinglish_p, rng.choice(INTENTS))))
                    t += rng.choice([4, 9, 15, 30, 45, 90, 240, 600]) * 1000 + rng.randrange(1000)
                speaker = (speaker + 1) % len(names) if len(names) > 2 else 1 - speaker
            last_end = t
    # A wall-clock time inside a DST overlap cannot be resolved by the parser; keep fixtures out of it.
    messages = [m for m in messages if not zone.is_ambiguous_local(m.utc_ms + zone.offset_at_utc(m.utc_ms) * MINUTE_MS)]
    specials = dict(zip(sorted(rng.sample(range(len(messages)), len(special_lines))), special_lines, strict=True))
    for i, m in enumerate(messages):
        roll = rng.random()
        if i in specials:
            m.text, m.special = specials[i], True
        elif roll < 0.03:
            m.kind, m.text = "Media", ""
        elif roll < 0.04:
            m.kind, m.text = "Deleted", ""
        elif roll < 0.06:
            m.edited = True
        elif roll < 0.10:
            m.text = m.text + "\n" + pick_line(rng, hinglish_p, "plain")
        if m.kind == "Text" and rng.random() < 0.05:
            m.reactions.append((1 - m.sender if len(names) == 2 else 0, rng.choice(["❤", "😂", "👍"])))
    return Chat(names, messages)


def special_lines(rng: random.Random, canary: str) -> list[str]:
    """Lines that the sanitizer and the canary test depend on; make_chat places them at seeded positions."""
    third = rng.choice(content.THIRD_PARTY_NAMES)
    phone = "9" + "".join(str(rng.randrange(10)) for _ in range(9))
    return [
        f"btw code word {canary} yaad rakhna",
        f"kal {third} ki party mein aa rahe ho?",
        f"mera naya number {phone[:5]} {phone[5:]} hai",
        "mail kar do zoya.test@example.com pe",
        "ye dekho https://example.com/trailer",
    ]


# ----------------------------------------------------------------- WhatsApp


@dataclass(frozen=True)
class WaStyle:
    os: str  # android | ios
    clock: str  # 12h | 24h
    order: str  # DMY | MDY
    year_digits: int = 2
    ampm_sep: str = NNBSP
    ampm_lower: bool = False


def wa_date(local: datetime, s: WaStyle) -> str:
    year = f"{local.year % 100:02d}" if s.year_digits == 2 else str(local.year)
    if s.order == "DMY":
        return f"{local.day:02d}/{local.month:02d}/{year}"
    return f"{local.month}/{local.day}/{year}"


def wa_time(local: datetime, s: WaStyle) -> str:
    secs = f":{local.second:02d}" if s.os == "ios" else ""
    if s.clock == "24h":
        return f"{local.hour:02d}:{local.minute:02d}{secs}"
    hour = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    if s.ampm_lower:
        ampm = ampm.lower()
    hh = f"{hour:02d}" if s.os == "ios" else str(hour)
    return f"{hh}:{local.minute:02d}{secs}{s.ampm_sep}{ampm}"


def wa_body(m: Message, s: WaStyle, self_index: int) -> str:
    if m.kind == "Media":
        return "<Media omitted>" if s.os == "android" else f"{LRM}image omitted"
    if m.kind == "Deleted":
        if s.os == "ios":
            return f"{LRM}This message was deleted."
        return "You deleted this message" if m.sender == self_index else "This message was deleted"
    if m.edited:
        return m.text + (" <This message was edited>" if s.os == "android" else f" {LRM}<This message was edited>")
    return m.text


def render_whatsapp(chat: Chat, zone: Zone, s: WaStyle) -> tuple[bytes, list[dict[str, object]]]:
    newline = "\r\n" if s.os == "ios" else "\n"
    precision_ms = 1000 if s.os == "ios" else MINUTE_MS
    lines: list[str] = []
    expected: list[dict[str, object]] = []

    def header(utc: int) -> str:
        local = datetime.fromtimestamp((utc + zone.offset_at_utc(utc) * MINUTE_MS) / 1000, UTC)
        stamp = f"{wa_date(local, s)}, {wa_time(local, s)}"
        return f"[{stamp}] " if s.os == "ios" else f"{stamp} - "

    first = chat.messages[0].utc_ms - 30_000
    if s.os == "android":
        lines.append(header(first) + ENCRYPTION_NOTICE)
    else:  # iOS attributes the notice to the chat (the other person's name)
        lines.append(header(first) + f"{chat.names[1]}: {LRM}{ENCRYPTION_NOTICE}")
    expected.append({"ts_utc_ms": first - first % precision_ms, "sender": None, "kind": "System", "text": ENCRYPTION_NOTICE, "edited": False})

    for m in chat.messages:
        body = wa_body(m, s, 0)
        lines.append(header(m.utc_ms) + f"{chat.names[m.sender]}: {body}")
        expected.append(
            {
                "ts_utc_ms": m.utc_ms - m.utc_ms % precision_ms,
                "sender": m.sender,
                "kind": m.kind,
                "text": m.text,
                "edited": m.edited,
            }
        )
    # Multi-line bodies already contain "\n", so convert once, after joining.
    data = ("\n".join(lines) + "\n").replace("\n", newline)
    return data.encode("utf-8"), expected


# ---------------------------------------------------------------- Instagram


def mojibake(text: str) -> str:
    """Meta writes UTF-8 bytes as Latin-1 code points, which json then escapes as \\u00XX."""
    return text.encode("utf-8").decode("latin-1")


def render_instagram(chat: Chat, thread: str, per_file: int) -> tuple[list[bytes], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    expected: list[dict[str, object]] = []
    for i, m in enumerate(chat.messages):
        if m.kind == "Deleted":
            continue  # IG has no deleted placeholder; unsent messages are simply absent
        ts = m.utc_ms
        rec: dict[str, object] = {"sender_name": mojibake(chat.names[m.sender]), "timestamp_ms": ts}
        kind, text = m.kind, m.text
        if m.kind == "Media":
            rec["photos"] = [{"uri": f"your_instagram_activity/messages/inbox/{thread}/photos/{i}.jpg", "creation_timestamp": ts // 1000}]
            text = ""
        elif i % 37 == 5 and not m.special:
            kind, text = "Link", ""
            rec["share"] = {"link": "https://www.instagram.com/p/EXAMPLE123/"}
            rec["content"] = mojibake(f"{chat.names[m.sender]} sent an attachment.")
        else:
            rec["content"] = mojibake(text)
        if m.reactions:
            rec["reactions"] = [{"reaction": mojibake(r), "actor": mojibake(chat.names[a])} for a, r in m.reactions]
        rec["is_geoblocked_for_viewer"] = False
        records.append(rec)
        expected.append(
            {
                "ts_utc_ms": ts,
                "sender": m.sender,
                "kind": kind,
                "text": text,
                "edited": False,
                "reactions": [{"actor": a, "emoji": r} for a, r in m.reactions],
            }
        )
    newest_first = list(reversed(records))
    parts = [newest_first[i : i + per_file] for i in range(0, len(newest_first), per_file)]
    files = []
    for part in parts:
        doc = {
            "participants": [{"name": mojibake(chat.names[1])}, {"name": mojibake(chat.names[0])}],
            "messages": part,
            "title": mojibake(chat.names[1]),
            "is_still_participant": True,
            "thread_path": f"inbox/{thread}",
            "magic_words": [],
        }
        files.append((json.dumps(doc, indent=2, ensure_ascii=True) + "\n").encode("ascii"))
    return files, expected


# ------------------------------------------------------------------ outputs


def by_first_appearance(names: list[str], messages: list[dict[str, object]]) -> tuple[list[str], int]:
    """Renumber senders (and reaction actors) to ParticipantId order; returns participants and SELF's id."""
    order: list[int] = []
    for m in sorted(messages, key=lambda m: m["ts_utc_ms"]):  # type: ignore[arg-type,return-value]
        sender = m["sender"]
        if isinstance(sender, int) and sender not in order:
            order.append(sender)
    remap = {old: new for new, old in enumerate(order)}
    for m in messages:
        if isinstance(m["sender"], int):
            m["sender"] = remap[m["sender"]]
        for r in m.get("reactions", []):  # type: ignore[attr-defined]
            r["actor"] = remap[r["actor"]]
    return [names[i] for i in order], remap[0]


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, doc: object) -> None:
    write(path, (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))


def stored_zip(path: Path, members: list[tuple[str, bytes]]) -> None:
    """ZIP_STORED with a fixed timestamp: deflate output differs between zlib builds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.create_system = 3  # unix, so the header bytes do not depend on the host OS
            z.writestr(info, data)


def main() -> None:
    seed_doc = json.loads((Path(__file__).parent / "seed.json").read_text(encoding="utf-8"))
    seed = int(seed_doc["seed"])
    master = random.Random(seed)
    canary = "lmcanary" + "".join(master.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(10))

    for out in (SYNTH, EXPECTED):
        shutil.rmtree(out, ignore_errors=True)

    manifest: list[dict[str, object]] = []

    def names_for(rng: random.Random, n: int = 2) -> list[str]:
        names = [rng.choice(content.SELF_NAMES), rng.choice(content.OTHER_NAMES)]
        while len(names) < n:
            extra = rng.choice(content.THIRD_PARTY_NAMES) + " " + rng.choice(["Kapoor", "Nair", "Das"])
            if extra not in names:
                names.append(extra)
        return names

    def add_whatsapp(
        fid: str,
        style: WaStyle,
        zone: Zone,
        start: datetime,
        days: int,
        *,
        n_people: int = 2,
        hinglish_p: float = 0.6,
        expect_code: str = "Ok",
        other_name: str | None = None,
        zip_name: str | None = None,
    ) -> None:
        rng = random.Random(f"{seed}:{fid}")
        names = names_for(rng, n_people)
        if other_name:
            names[1] = other_name
        chat = make_chat(rng, names, zone, start, days, hinglish_p, special_lines(rng, canary))
        data, msgs = render_whatsapp(chat, zone, style)
        participants, self_id = by_first_appearance(names, msgs)
        rel = f"whatsapp/{style.os}/{fid}/_chat.txt"
        write(SYNTH / rel, data)
        files = [rel]
        if zip_name:
            zrel = f"zips/{zip_name}"
            stored_zip(SYNTH / zrel, [("_chat.txt", data)])
            files.append(zrel)
        expected = {
            "id": fid,
            "platform": "whatsapp",
            "dialect": style.os,
            "files": files,
            "context": {"date_order": style.order, "tz": zone.name, "transitions": zone.transitions()},
            "expect_code": expect_code,
            "participants": participants,
            "self_id": self_id,
            "message_count": len(msgs),
            "messages": msgs,
        }
        write_json(EXPECTED / f"{fid}.json", expected)
        manifest.append({"id": fid, "platform": "whatsapp", "files": files, "participants": names, "expect_code": expect_code})

    start = datetime(2026, 6, 1, 0, 0)
    add_whatsapp("android_12h_dmy", WaStyle("android", "12h", "DMY", ampm_sep=" ", ampm_lower=True), KOLKATA, start, 75)
    add_whatsapp("android_12h_mdy", WaStyle("android", "12h", "MDY"), KOLKATA, start, 75, hinglish_p=0.2)
    add_whatsapp("android_24h_dmy", WaStyle("android", "24h", "DMY", year_digits=4), KOLKATA, start, 75)
    add_whatsapp("android_24h_mdy", WaStyle("android", "24h", "MDY"), KOLKATA, start, 75, hinglish_p=0.1)
    add_whatsapp("ios_12h_dmy", WaStyle("ios", "12h", "DMY"), KOLKATA, start, 75, zip_name="whatsapp_ios_12h_dmy.zip")
    add_whatsapp("ios_12h_mdy", WaStyle("ios", "12h", "MDY"), KOLKATA, start, 75, hinglish_p=0.2)
    add_whatsapp("ios_24h_dmy", WaStyle("ios", "24h", "DMY"), KOLKATA, start, 75)
    add_whatsapp("ios_24h_mdy", WaStyle("ios", "24h", "MDY"), KOLKATA, start, 75, hinglish_p=0.1, other_name="+91 98765 01234")
    add_whatsapp("android_24h_dmy_london_dst", WaStyle("android", "24h", "DMY"), LONDON, datetime(2026, 10, 1), 50, hinglish_p=0.3)
    # Days 1-11 of March (plus spill-over to the 12th): every field is <= 12 and both DMY and MDY
    # readings are monotonic, so the order cannot be inferred and the UI must ask.
    add_whatsapp(
        "android_ambiguous_date_order",
        WaStyle("android", "12h", "DMY", ampm_sep=" ", ampm_lower=True),
        KOLKATA,
        datetime(2026, 3, 1),
        11,
        expect_code="AmbiguousDateOrder",
    )
    add_whatsapp("android_group_3p", WaStyle("android", "24h", "DMY"), KOLKATA, start, 20, n_people=3, expect_code="GroupChatRejected")
    add_whatsapp("ios_trailer_small", WaStyle("ios", "24h", "DMY"), KOLKATA, start, 9)

    for fid, days, per_file in (("instagram_split_mojibake", 75, 400), ("instagram_single", 30, 10_000)):
        rng = random.Random(f"{seed}:{fid}")
        names = names_for(rng)
        chat = make_chat(rng, names, KOLKATA, start, days, 0.5, special_lines(rng, canary))
        parts, msgs = render_instagram(chat, "thread_1234567890", per_file)
        participants, self_id = by_first_appearance(names, msgs)
        files = []
        for i, data in enumerate(parts, start=1):
            rel = f"instagram/{fid}/message_{i}.json"
            write(SYNTH / rel, data)
            files.append(rel)
        zrel = f"zips/{fid}.zip"
        stored_zip(SYNTH / zrel, [(f"your_instagram_activity/messages/inbox/thread_1234567890/message_{i}.json", d) for i, d in enumerate(parts, start=1)])
        files.append(zrel)
        expected = {
            "id": fid,
            "platform": "instagram",
            "dialect": None,
            "files": files,
            "context": {"date_order": None, "tz": KOLKATA.name, "transitions": KOLKATA.transitions()},
            "expect_code": "MojibakeRepaired",
            "participants": participants,
            "self_id": self_id,
            "message_count": len(msgs),
            "messages": msgs,
        }
        write_json(EXPECTED / f"{fid}.json", expected)
        manifest.append({"id": fid, "platform": "instagram", "files": files, "participants": names, "expect_code": "MojibakeRepaired"})

    pii_rows = pii.generate(random.Random(f"{seed}:pii"))
    write(ROOT / "pii" / "labelled_in.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pii_rows).encode("utf-8"))

    write_json(ROOT / "manifest.json", {"seed": seed, "canary": canary, "fixtures": manifest})
    print(f"wrote {len(manifest)} fixtures and {len(pii_rows)} PII rows (seed {seed})")


if __name__ == "__main__":
    main()
