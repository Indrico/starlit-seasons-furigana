# Extracting the local Japanese dialogue

These tools prepare private input for the furigana generator. They do not install
the renderer, modify a game archive, alter the executable, or change Steam
activation. Start the owned game normally through Steam before recovering its
resource key. The on-disk Shipping executable has an encrypted `.text` section;
the recovery tool reads the normally loaded module instead of patching that file.

## Requirements

- Windows x64 and 64-bit Python 3.10 or newer.
- `pycryptodome` providing `Crypto.Cipher.AES`.
- The installed game files. The verified target is Steam build `8278842`, UE 4.24.
- Enough free space for the selected private assets and generated data.

The recovery command requires an explicit process ID and game root. It checks
that the selected process contains the expected executable at that exact path
before reading its `.text`. It requests query/read access only and closes both
process and module-snapshot handles. It neither launches nor injects into a process.

## Commands

Install `requirements.txt` using the README's virtual-environment setup first.
Run these commands from the project root. Choose a private output directory
outside the repository, and keep the game open for the first command only.

```powershell
$gameRoot = 'D:\SteamLibrary\steamapps\common\StarlitSeason'
$privateRoot = 'D:\StarlitFurigana-private'
Get-Process -Name 'StarlitSeason-Win64-Shipping' | Select-Object Id, Path

# Replace 12345 with the explicitly selected running game's process ID.
& '.\.venv\Scripts\python.exe' tools/extraction/recover_local_pak_key.py --pid 12345 --game "$gameRoot" --pak "$gameRoot/StarlitSeason/Content/Paks/pakchunk0-WindowsNoEditor.pak" --output "$privateRoot/evidence"
& '.\.venv\Scripts\python.exe' tools/extraction/extract_original.py --game "$gameRoot" --key-file "$privateRoot/evidence/pak-key.hex" --output "$privateRoot/original"
& '.\.venv\Scripts\python.exe' tools/extraction/corpus_extract.py --input "$privateRoot/original/StarlitSeason/Content/Commu/Localize" --output "$privateRoot/corpus"
& '.\.venv\Scripts\python.exe' tools/extraction/localization_extract.py --content "$privateRoot/original/StarlitSeason/Content" --output "$privateRoot"
```

`extract_original.py` reads only the original `pakchunk*-WindowsNoEditor.pak`
archives. It excludes `~mods`, preserving Japanese input even when an English
patch is installed. Mount points are resolved into one content tree. Later
installed chunks replace earlier versions of the same selected resource.
Selection includes Commu localization tables, Commu widgets, font/style assets,
the character profile table, and Japanese localization resources.

Every encrypted directory index must pass its embedded SHA1 check before the
tool interprets entries or extracts members. A candidate key is accepted only
after this check; entropy or a byte-pattern match alone is insufficient.
Extraction destinations are checked to prevent archive paths escaping the
explicit output directory.

## Generated interfaces

`corpus/dialogue.jsonl` contains one JSON object per nonempty Japanese table row:

```json
{"asset":"Example/CML_example.uasset","row_id":"example_001","source_text":"今日の予定です。","character":"話者","source_sha256":"SHA256_OF_EXACT_UTF8_SOURCE"}
```

The example above is synthetic. `asset` is relative to the selected CML input
root. Text is taken specifically from `Japanese` string properties; newlines,
control tags, placeholders, and spacing are preserved. Strings in the other
language columns are not used as Japanese source. Row counts, property lengths,
name-table indexes, and export termination are validated. A table parse failure
is included in `corpus-report.json` and causes a nonzero exit code.

`localization-ja.json` resolves the installed game JA LocRes keys.
`character-profiles-resolved.json` contains the profile rows with localization
references resolved, including canonical full names and the `Ruby` readings that
the game actually supplies. Empty source readings remain empty.

The PAK recovery key, provenance, archive manifests, original assets, complete
dialogue corpus, localized strings, and memory captures are private generated
inputs. Do not commit or redistribute them. None is needed to run the synthetic
source tests.

## Validation performed

On the selected installed build:

- All nine original PAK directory indexes passed their embedded SHA1 checks.
- All 163 extracted CML DataTables parsed with zero errors.
- The corpus contains 59,361 nonempty Japanese rows and 53,567 distinct strings.
- The profile resolver read 40 character rows and 11,788 game localization entries.
- An independently installed `repak` 0.2.3 produced identical bytes for one
  original CML `.uasset`/`.uexp` pair, including its compressed encrypted content.

The six synthetic tests cover stored/compressed and encrypted PAK members,
absolute versus relative block offsets, bad keys and corrupt indexes, archive
path traversal, exact Japanese text preservation, unparsed DataTable tails, and
LocRes resolution. Run them with:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tools/extraction -p test_extraction.py -v
```

These checks establish extraction and parsing. They do not establish renderer
compatibility, visual quality, or the correctness of automatically generated
readings.

## Format references

- [repak](https://github.com/trumank/repak), independent Unreal PAK reader.
- [CUE4Parse localization reader](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Localization/FTextLocalizationResource.cs),
  reference for compact LocRes resources and text keys.
