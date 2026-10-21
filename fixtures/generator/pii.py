"""Labelled Indian PII set for the sanitizer's recall bar (>= 99%).

Each row: {"id", "text", "spans": [{"start", "end", "label", "value"}]}, with
start/end as UTF-8 byte offsets (the engine scans bytes). Every value is
synthetic: example/test domains, random digits, invented handles.
Labels match the mask tokens: PHONE EMAIL UPI LINK HANDLE ID NUM NAME.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import content

Gen = Callable[[random.Random], str]


def digits(rng: random.Random, n: int, first: str = "0123456789") -> str:
    return rng.choice(first) + "".join(rng.choice("0123456789") for _ in range(n - 1))


def mobile(rng: random.Random) -> str:
    return digits(rng, 10, first="6789")


PHONE_FORMS: list[Gen] = [
    lambda r: mobile(r),
    lambda r: "+91" + mobile(r),
    lambda r: (lambda m: f"+91 {m[:5]} {m[5:]}")(mobile(r)),
    lambda r: (lambda m: f"+91-{m[:5]}-{m[5:]}")(mobile(r)),
    lambda r: (lambda m: f"0{m[:5]} {m[5:]}")(mobile(r)),
    lambda r: (lambda m: f"{m[:5]}-{m[5:]}")(mobile(r)),
    lambda r: (lambda m: f"{m[:5]} {m[5:]}")(mobile(r)),
    lambda r: (lambda m: f"+91 {m[:3]} {m[3:6]} {m[6:]}")(mobile(r)),
]
USERS = ["riya", "kabir.m", "ananya_v", "dev99", "zoya.k", "meera.iyer", "noor", "arjun_s"]


def email(r: random.Random) -> str:
    return f"{r.choice(USERS)}{r.randrange(100)}@{r.choice(['example.com', 'example.org', 'mail.test', 'example.in'])}"


def upi(r: random.Random) -> str:
    handle = r.choice([r.choice(USERS), mobile(r)])
    return f"{handle}@{r.choice(['okaxis', 'ybl', 'paytm', 'oksbi', 'ibl', 'okhdfcbank', 'upi'])}"


def link(r: random.Random) -> str:
    path = "".join(r.choice("abcdefghijkmnpqrstuvwxyz0123456789") for _ in range(6))
    return r.choice(
        [
            f"https://example.com/{path}",
            f"http://example.org/p/{path}?ref=chat",
            f"www.example.com/{path}",
            f"example.in/{path}",
            f"https://www.instagram.com/p/{path}/",
        ]
    )


def handle(r: random.Random) -> str:
    return "@" + r.choice(USERS) + r.choice(["", "_", "."]) + str(r.randrange(10, 99))


def aadhaar(r: random.Random) -> str:
    d = digits(r, 12, first="23456789")
    return r.choice([d, f"{d[:4]} {d[4:8]} {d[8:]}", f"{d[:4]}-{d[4:8]}-{d[8:]}"])


def pan(r: random.Random) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(r.choice(letters) for _ in range(3)) + "P" + r.choice(letters) + digits(r, 4) + r.choice(letters)


def num(r: random.Random) -> str:
    return r.choice([digits(r, 6, first="1234567"), digits(r, 4, first="123456789"), digits(r, 5, first="123456789")])


GENERATORS: dict[str, list[Gen]] = {
    "PHONE": PHONE_FORMS,
    "EMAIL": [email],
    "UPI": [upi],
    "LINK": [link],
    "HANDLE": [handle],
    "ID": [aadhaar, pan],
    "NUM": [num],
    "NAME": [lambda r: r.choice(content.THIRD_PARTY_NAMES)],
}

TEMPLATES: dict[str, list[str]] = {
    "PHONE": ["mera number {} hai", "call me on {}", "{} pe whatsapp karo", "papa ka number {} save kar lo"],
    "EMAIL": ["mail kar do {} pe", "send the notes to {}", "{} is my new id"],
    "UPI": ["pay kar do {} pe", "gpay {} please", "send 500 to {}"],
    "LINK": ["ye dekho {}", "check this {}", "{} lol"],
    "HANDLE": ["insta pe follow karo {}", "{} is so funny", "tag {} in the post"],
    "ID": ["mera aadhaar {} hai", "PAN {} bhej raha hoon", "id number: {}"],
    "NUM": ["pin code {} likhna", "OTP {} hai", "bill aaya {} ka", "room {} mein aa jao"],
    "NAME": ["kal {} ki party hai", "{} told me everything", "{} ko mat batana", "met {} at the cafe"],
}

# Things a sanitizer must leave alone (no spans): short numbers, times, dates, everyday words.
NEGATIVES = [
    "kal 3 baje milte hain",
    "meeting at 9:30 tomorrow",
    "21/10 ko exam hai",
    "only 2 days left",
    "asha hai sab theek hoga",
    "room no 12 pe aa jao",
    "class 10 ke notes",
    "I scored 98 in maths",
    "haha 😂😂",
    "train is at 7:45",
    "@ the mall, come fast",
    "see you at 11",
]


def build(rng: random.Random, parts: list[tuple[str, str | None]]) -> dict[str, object]:
    """Concatenate (text, label) parts, recording UTF-8 byte spans for labelled parts."""
    out = b""
    spans = []
    for text, label in parts:
        encoded = text.encode("utf-8")
        if label:
            spans.append({"start": len(out), "end": len(out) + len(encoded), "label": label, "value": text})
        out += encoded
    return {"text": out.decode("utf-8"), "spans": spans}


def single(rng: random.Random, label: str) -> dict[str, object]:
    template = rng.choice(TEMPLATES[label])
    value = rng.choice(GENERATORS[label])(rng)
    before, after = template.split("{}")
    if rng.random() < 0.2:
        after += " " + rng.choice(content.EMOJIS)
    return build(rng, [(before, None), (value, label), (after, None)])


def generate(rng: random.Random) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    labels = list(GENERATORS)
    for label in labels:
        for _ in range(45):
            rows.append(single(rng, label))
    for _ in range(40):  # two entities in one message
        a, b = rng.choice(labels), rng.choice(labels)
        first, second = single(rng, a), single(rng, b)
        rows.append(build(rng, [(str(first["text"]), None), (" aur ", None), (str(second["text"]), None)]))
        shift = len((str(first["text"]) + " aur ").encode("utf-8"))
        rows[-1]["spans"] = list(first["spans"]) + [  # type: ignore[call-overload]
            {**s, "start": s["start"] + shift, "end": s["end"] + shift} for s in second["spans"]  # type: ignore[attr-defined]
        ]
    for text in NEGATIVES:
        rows.append({"text": text, "spans": []})
    return [{"id": f"pii-{i:04d}", **row} for i, row in enumerate(rows)]
