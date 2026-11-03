# Offline reading pipeline

`tools/readings/generate.py` creates furigana candidates from original local Japanese text. It does not install a mod, modify game files, or render text by itself.

## Inputs and generation

Use the setup commands in the repository README. The implemented command is:

```powershell
& '.\.venv\Scripts\python.exe' tools/readings/generate.py .local/extracted/corpus/dialogue.jsonl --profiles .local/extracted/character-profiles-resolved.json --output .local/generated
```

Those input paths are examples. If you used the external private directory in
[the extraction guide](asset-extraction.md), use its `corpus/dialogue.jsonl` and
`character-profiles-resolved.json` paths instead.

The corpus is either a JSON array or JSONL file containing records like this synthetic example:

```json
{"asset":"/Game/Commu/Localize/example","row_id":"example_001","source_text":"学校へ行く"}
```

`source_text` is required; `asset` and `row_id` are preserved when present. The optional `--profiles` file is a JSON array of original character profile records containing `Kan_Full` and `Ruby`. Nonempty profile readings take priority over the supplied manual character-name overrides. Spaced and compact full-name forms are supported.

The default overrides file is `tools/readings/overrides.json`. Use `--overrides PATH` to supply another local file with `phrases` and `tokens` maps from written forms to kana readings.

For a narrow correction, `source_tokens` maps an exact source text's UTF-8 SHA-256
to token readings. Use the extracted record's `source_sha256` value as the key.
For example, replace `EXACT_SOURCE_SHA256` in this structure with that hash:

```json
{"source_tokens":{"EXACT_SOURCE_SHA256":{"今日":"きょう"}}}
```

These corrections take priority over global token readings only for the matching
source string. Existing phrase/name matches remain unchanged. The shipped
override corrects `今日` in one observed reunion dialogue line; it does not
change the tokenizer's choice for `今日` elsewhere. A hash key avoids copying the
complete game line into the override file.

## Processing rules

- SudachiPy 0.6.11 and SudachiDict-core 20241021 are pinned together. The later 0.7 dictionary-format transition is intentionally outside this implementation.
- The exact source text is retained. Concatenating every output segment's `base` must reconstruct it byte-for-byte when encoded as UTF-8; the generator raises an error on a mismatch.
- Kanji compounds share a reading. Kana anchors split inflected forms, for example `食べ物` becomes `食/た`, `べ`, `物/もの`.
- Tags, substitution placeholders, escaped controls, and actual line breaks are preserved as `control=true` segments without readings. The actual extracted corpus contained only `<pop_G>` and `</>` rich-text tags, 41 pairs in total.
- Known full names and multi-character given names are matched before tokenization because the tokenizer can split names such as 心白 into ordinary words. Single-character name overrides apply only to whole tokens.
- The token `私` defaults to the common reading `わたし`; compounds such as `私立` retain their dictionary reading. Formal character-specific `わたくし` remains a contextual review case.
- Out-of-dictionary words and failed alignments keep their original text without an invented reading and are reported for review.

## Outputs

All generated outputs should remain under the ignored `.local/` directory.

| File | Contents |
| --- | --- |
| `readings.json` | Source text, asset/row identity, source SHA-256, and segments |
| `readings.lua` | Lua table keyed by exact source text, with segment arrays as values |
| `coverage.json` | Counts, dependency versions, effective override hash, and review status |
| `unresolved.json` | Source records with out-of-dictionary or alignment failures |

Example Lua value:

```lua
return {
  ["学校へ行く"] = {
    {base="学校", reading="がっこう"},
    {base="へ"},
    {base="行", reading="い"},
    {base="く"},
  },
}
```

Plain segments may be combined. Lua control bytes use fixed-width decimal escapes, and Japanese characters remain UTF-8. Runtime code must interpret controls according to game behavior rather than displaying raw markup.

## Validation and limitations

The eleven tests cover common contextual readings, okurigana, original-text preservation, controls, all supplied given-name overrides, the pronoun/compound boundary, the exact-source `今日再会` correction, small katakana inside surnames, supplementary Unicode, Lua escaping, and duplicate records with separate provenance.

The local build processed 59,361 records, including 53,567 unique source texts. It produced candidate readings for 258,766 of 259,130 visible kanji characters, approximately 99.86%, with 362 records containing unresolved cases. This measures candidate coverage, not linguistic correctness. Zero complete records were manually reviewed.

Unresolved groups include counters and numerals, ambiguous `１日`, and expressive elongated spelling. For example, blindly using a dictionary reading of `ついたち` for every `１日` would be wrong in a sentence meaning “one day.” These cases remain visible in the report. Exact-text lookup also does not distinguish identical lines spoken by characters with different preferred readings, resolve arbitrary player-entered names, or handle text changed by a later game update.

Original character readings are local input. The source-only overrides file also uses names and romanizations from the [official character listing](https://starlit-season.idolmaster.jp/idol/). No original dialogue corpus, generated lookup table, character profile asset, or encryption key is included in this repository.
