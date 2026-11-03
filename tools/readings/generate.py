"""Build exact-source furigana candidates; never rewrite the game text.

Inputs: JSON array or JSONL records with asset, row_id, source_text.
Outputs: JSON provenance, a Lua exact-text lookup, and unresolved-case report.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
from typing import Iterable

from sudachipy import dictionary, tokenizer


KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002ffff\U00030000-\U000323af々〆]")
# ヶ/ヵ inside names such as 城ヶ崎 are pronounced が/か rather than literal け.
RUNS = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002ffff\U00030000-\U000323af々〆ヶヵ]+|[^\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002ffff\U00030000-\U000323af々〆ヶヵ]+")
# Preserve markup and substitution syntax verbatim, including their attributes.
CONTROLS = re.compile(r"<[^<>\r\n]*>|\{[^{}\r\n]*\}|%\d*\$?[sdif]|\\[nrt]|\r\n|\r|\n")
KANA_READING = re.compile(r"[ぁ-ゖーゝゞ]+\Z")


def hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def align(surface: str, reading: str) -> list[dict] | None:
    """Align kana anchors so 食べ物 becomes 食/た + べ + 物/もの.

    A compound kanji run stays together; impossible alignments remain unresolved.
    """
    pieces = RUNS.findall(surface)
    pattern = "".join("(.+?)" if KANJI.search(p) else re.escape(hiragana(p)) for p in pieces)
    matched = re.fullmatch(pattern, hiragana(reading))
    if not matched:
        return None
    readings = iter(matched.groups())
    result = []
    for piece in pieces:
        segment = {"base": piece}
        if KANJI.search(piece):
            kana = next(readings)
            if not KANA_READING.fullmatch(kana):
                return None
            segment["reading"] = kana
        result.append(segment)
    return result


class Annotator:
    def __init__(self, overrides: dict | None = None):
        self.tokenizer = dictionary.Dictionary().create()
        self.overrides = overrides or {}
        self.tokens = self.overrides.get("tokens", {})
        self.source_tokens = self.overrides.get("source_tokens", {})
        # Sudachi may split uncommon names (心白, 摩美々) into ordinary words.
        # Multi-character name overrides therefore run before tokenization;
        # single-character overrides remain token-only to preserve 真っ赤 etc.
        self.phrases = {
            **{surface: reading for surface, reading in self.tokens.items() if len(surface) > 1},
            **self.overrides.get("phrases", {}),
        }
        alternatives = sorted(self.phrases, key=lambda text: (-len(text), text))
        self.phrase_pattern = re.compile("|".join(map(re.escape, alternatives))) if alternatives else None

    def annotate(self, source: str) -> tuple[list[dict], list[dict]]:
        segments: list[dict] = []
        issues: list[dict] = []
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        contextual_tokens = self.source_tokens.get(source_hash, {})

        def append(segment: dict):
            if not segment["base"]:
                return
            if (segments and len(segment) == 1 and len(segments[-1]) == 1):
                segments[-1]["base"] += segment["base"]
            else:
                segments.append(segment)

        def tokenize_part(text: str):
            for morpheme in self.tokenizer.tokenize(text, tokenizer.Tokenizer.SplitMode.C):
                surface = morpheme.surface()
                if not KANJI.search(surface):
                    append({"base": surface})
                    continue
                overridden = surface in contextual_tokens or surface in self.tokens
                reading = contextual_tokens.get(surface, self.tokens.get(surface, morpheme.reading_form()))
                if morpheme.is_oov() and not overridden:
                    append({"base": surface})
                    issues.append({"surface": surface, "reason": "out_of_dictionary"})
                    continue
                aligned = align(surface, reading)
                if aligned is None:
                    append({"base": surface})
                    issues.append({"surface": surface, "candidate_reading": hiragana(reading), "reason": "alignment_failed"})
                    continue
                for segment in aligned:
                    append(segment)

        def plain_part(text: str):
            cursor = 0
            for match in self.phrase_pattern.finditer(text) if self.phrase_pattern else ():
                tokenize_part(text[cursor:match.start()])
                surface = match.group()
                aligned = align(surface, self.phrases[surface])
                if aligned is None:
                    append({"base": surface})
                    issues.append({"surface": surface, "reason": "override_alignment_failed"})
                else:
                    for segment in aligned:
                        append(segment)
                cursor = match.end()
            tokenize_part(text[cursor:])

        cursor = 0
        for match in CONTROLS.finditer(source):
            plain_part(source[cursor:match.start()])
            append({"base": match.group(), "control": True})
            cursor = match.end()
        plain_part(source[cursor:])
        reconstructed = "".join(segment["base"] for segment in segments)
        if reconstructed != source:
            raise ValueError("Tokenizer did not preserve source text exactly")
        return segments, issues


def load_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if text.lstrip().startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def lua_string(text: str) -> str:
    # UTF-8 stays literal; control bytes use fixed-width Lua decimal escapes.
    result = ['"']
    for char in text:
        if char in ('"', "\\"):
            result.append("\\" + char)
        elif ord(char) < 32 or ord(char) == 127:
            result.append(f"\\{ord(char):03d}")
        else:
            result.append(char)
    return "".join(result) + '"'


def write_lua(path: Path, entries: Iterable[tuple[str, list[dict]]]):
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write("-- Generated exact-source furigana candidates; see coverage.json.\nreturn {\n")
        for source, segments in entries:
            output.write(f"[{lua_string(source)}]={{")
            for segment in segments:
                fields = [f"base={lua_string(segment['base'])}"]
                if "reading" in segment:
                    fields.append(f"reading={lua_string(segment['reading'])}")
                if segment.get("control"):
                    fields.append("control=true")
                output.write("{" + ",".join(fields) + "},")
            output.write("},\n")
        output.write("}\n")


def build(corpus: list[dict], output: Path, overrides: dict) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    annotator = Annotator(overrides)
    lookup: dict[str, tuple[list[dict], list[dict]]] = {}
    records = []
    unresolved = []
    for item in corpus:
        source = item["source_text"]
        if not isinstance(source, str):
            raise TypeError("source_text must be a string")
        if source not in lookup:
            lookup[source] = annotator.annotate(source)
        segments, issues = lookup[source]
        record = {key: item[key] for key in ("asset", "row_id") if key in item}
        record.update(source_text=source, source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(), segments=segments)
        records.append(record)
        if issues:
            unresolved.append({**{key: record[key] for key in ("asset", "row_id") if key in record}, "source_text": source, "issues": issues})
    total_kanji = sum(len(KANJI.findall(s["base"])) for segments, _ in lookup.values() for s in segments if not s.get("control"))
    annotated_kanji = sum(len(KANJI.findall(s["base"])) for segments, _ in lookup.values() for s in segments if s.get("reading"))
    coverage = {
        "input_records": len(corpus), "unique_source_texts": len(lookup),
        "unique_texts_with_readings": sum(any(s.get("reading") for s in segments) for segments, _ in lookup.values()),
        "kanji_characters_unique_sources": total_kanji,
        "annotated_kanji_characters_unique_sources": annotated_kanji,
        "records_with_unresolved_cases": len(unresolved),
        "manually_reviewed_records": 0,
        "status": "machine_generated_candidates_require_context_review",
        "overrides_sha256": hashlib.sha256(json.dumps(overrides, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "versions": {name: importlib.metadata.version(name) for name in ("SudachiPy", "SudachiDict-core")},
    }
    for filename, value in (("readings.json", records), ("unresolved.json", unresolved), ("coverage.json", coverage)):
        (output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    write_lua(output / "readings.lua", ((source, value[0]) for source, value in lookup.items()))
    return coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated")
    parser.add_argument("--overrides", type=Path, default=Path(__file__).parent / "overrides.json")
    parser.add_argument("--profiles", type=Path, help="Extracted original character profiles with Kan_Full and Ruby")
    args = parser.parse_args()
    overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides.exists() else {}
    if args.profiles:
        profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
        for profile in profiles:
            name, reading = profile.get("Kan_Full", ""), profile.get("Ruby", "")
            if name and reading:
                overrides.setdefault("phrases", {})[name] = reading
                overrides["phrases"][name.replace(" ", "").replace("　", "")] = reading.replace(" ", "").replace("　", "")
        overrides["profile_source_sha256"] = hashlib.sha256(args.profiles.read_bytes()).hexdigest()
    print(json.dumps(build(load_records(args.corpus), args.output, overrides), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
