"""Invariants of the generated corpus. Run: python -m unittest discover -s fixtures/generator"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = Path(__file__).resolve().parent / "gen.py"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def expected(fid: str) -> dict:
    return json.loads((ROOT / "expected" / f"{fid}.json").read_text(encoding="utf-8"))


def raw_files(fid: str) -> list[Path]:
    entry = next(f for f in MANIFEST["fixtures"] if f["id"] == fid)
    return [ROOT / "synthetic" / rel for rel in entry["files"] if not rel.endswith(".zip")]


def tree_digest() -> str:
    h = hashlib.sha256()
    for path in sorted(p for d in ("synthetic", "expected", "pii") for p in (ROOT / d).rglob("*") if p.is_file()):
        h.update(path.relative_to(ROOT).as_posix().encode())
        h.update(path.read_bytes())
    h.update((ROOT / "manifest.json").read_bytes())
    return h.hexdigest()


class Determinism(unittest.TestCase):
    def test_regenerating_is_byte_identical(self) -> None:
        before = tree_digest()
        subprocess.run([sys.executable, str(GEN)], check=True, capture_output=True)
        self.assertEqual(before, tree_digest())


class Corpus(unittest.TestCase):
    def test_canary_is_in_every_fixture(self) -> None:
        canary = MANIFEST["canary"]
        self.assertRegex(canary, r"^lmcanary[a-z]{10}$")  # letters only, so no mask rule can hide it
        for f in MANIFEST["fixtures"]:
            texts = [m["text"] for m in expected(f["id"])["messages"]]
            self.assertEqual(sum(canary in t for t in texts), 1, f["id"])

    def test_full_fixtures_clear_trailer_thresholds(self) -> None:
        for fid in ("android_12h_dmy", "android_12h_mdy", "android_24h_dmy", "android_24h_mdy",
                    "ios_12h_dmy", "ios_12h_mdy", "ios_24h_dmy", "ios_24h_mdy",
                    "android_24h_dmy_london_dst", "instagram_split_mojibake"):
            ms = expected(fid)["messages"]
            ts = [m["ts_utc_ms"] for m in ms]
            self.assertGreaterEqual(len(ms), 300, fid)
            self.assertGreaterEqual((max(ts) - min(ts)) / 86_400_000, 14, fid)

    def test_trailer_fixture_is_small(self) -> None:
        self.assertLess(expected("ios_trailer_small")["message_count"], 300)

    def test_group_fixture_has_three_people(self) -> None:
        self.assertEqual(len(expected("android_group_3p")["participants"]), 3)

    def test_ambiguous_fixture_never_exceeds_12_in_a_date_field(self) -> None:
        text = raw_files("android_ambiguous_date_order")[0].read_text(encoding="utf-8")
        fields = re.findall(r"^(\d{2})/(\d{2})/\d{2}, ", text, flags=re.M)
        self.assertTrue(fields)
        self.assertTrue(all(int(a) <= 12 and int(b) <= 12 for a, b in fields))

    def test_dst_fixture_spans_both_offsets_and_avoids_the_overlap(self) -> None:
        d = expected("android_24h_dmy_london_dst")
        change = d["context"]["transitions"][1]
        self.assertEqual(change["offset_min"], 0)
        ts = [m["ts_utc_ms"] for m in d["messages"]]
        start_utc = (change["from_local_min"] - change["offset_min"]) * 60_000
        self.assertTrue(min(ts) < start_utc < max(ts))
        overlap = (start_utc - 3_600_000, start_utc + 3_600_000)  # UTC instants whose local time repeats
        self.assertFalse(any(overlap[0] <= t < overlap[1] for t in ts))

    def test_line_endings_follow_dialect(self) -> None:
        for f in MANIFEST["fixtures"]:
            if f["platform"] != "whatsapp":
                continue
            data = raw_files(f["id"])[0].read_bytes()
            if "/ios/" in f["files"][0]:
                self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), f["id"])
            else:
                self.assertNotIn(b"\r", data, f["id"])

    def test_instagram_is_mojibake_newest_first_and_split(self) -> None:
        files = raw_files("instagram_split_mojibake")
        self.assertGreater(len(files), 1)
        stamps = []
        for path in files:
            raw = path.read_bytes()
            self.assertTrue(raw.isascii())
            self.assertIn(b"\\u00f0\\u009f", raw)  # an emoji's UTF-8 bytes escaped as Latin-1
            stamps += [m["timestamp_ms"] for m in json.loads(raw)["messages"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_hinglish_is_present(self) -> None:
        texts = " ".join(m["text"] for m in expected("android_12h_dmy")["messages"])
        for word in ("kya", "haan", "yaar"):
            self.assertIn(word, texts)


class PiiSet(unittest.TestCase):
    rows = [json.loads(line) for line in (ROOT / "pii" / "labelled_in.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_spans_are_utf8_byte_offsets_of_their_values(self) -> None:
        for row in self.rows:
            raw = row["text"].encode("utf-8")
            for s in row["spans"]:
                self.assertEqual(raw[s["start"] : s["end"]].decode("utf-8"), s["value"], row["id"])

    def test_every_label_is_well_represented(self) -> None:
        counts: dict[str, int] = {}
        for row in self.rows:
            for s in row["spans"]:
                counts[s["label"]] = counts.get(s["label"], 0) + 1
        self.assertEqual(sorted(counts), ["EMAIL", "HANDLE", "ID", "LINK", "NAME", "NUM", "PHONE", "UPI"])
        self.assertTrue(all(n >= 45 for n in counts.values()), counts)

    def test_negatives_exist(self) -> None:
        self.assertGreaterEqual(sum(not r["spans"] for r in self.rows), 10)


if __name__ == "__main__":
    unittest.main()
