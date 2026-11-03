# Agent guide

This is the handoff and working guide for AI agents contributing to Starlit
Season Furigana. The status below was verified on **2026-11-03**. Recheck Git,
release metadata, and the local installation before treating that status as
current. Keep repository documentation, release notes, and usage instructions
in **English**.

## Start here

1. Read this file, [README.md](README.md), and [runtime verification](docs/runtime.md).
2. Inspect `git status --short --branch` and the relevant implementation before
   editing. Preserve unrelated changes and the user's game files.
3. For player support, use the [drag-and-drop guide](docs/usage.md). Players do
   not need Python, extraction tools, or a build environment.
4. For development, follow [build from source](docs/build-from-source.md),
   [installation](docs/installation.md), and the tests listed below.
5. Make focused changes, validate the affected behavior, and report what was
   actually tested. Do not infer visual or input compatibility from unit tests.

## What has been completed

- Reverse-engineered the original Japanese conversation tables, widget paths,
  and build-specific loader signatures. The investigation followed the
  [REA guide](https://github.com/morluto/rea). See
  [reverse-engineering notes](docs/reverse-engineering.md) for evidence.
- Implemented local PAK extraction, CML/LocRes parsing, character-reading
  resolution, and an offline Sudachi reading generator.
- Implemented a UE4SS Lua renderer for Japanese dialogue and answer labels,
  including kana layout, wrapping, font fitting, source matching, native
  typewriter preservation, and the F7 toggle.
- Added a reversible Python installer and a self-contained Windows release with
  a checker, uninstaller, pinned loader, and prebuilt annotations.
- Published **[v0.1.0-alpha.2](https://github.com/Indrico/starlit-seasons-furigana/releases/tag/v0.1.0-alpha.2)**
  as a prerelease. It replaces the source-only installation experience of
  `v0.1.0-alpha.1`; the older release remains available historically.

Implementation history:

| Commit | Result |
| --- | --- |
| `08599b8` | Initial dialogue/choice mod, extraction, readings, installer, and tests |
| `b1bae42` | First alpha release documentation and English usage guide |
| `da2fa2d` | Tested drag-and-drop Windows package and annotation-only lookup |

The public repository is
`https://github.com/Indrico/starlit-seasons-furigana.git`, with development on
`main`. The `v0.1.0-alpha.2` tag points to
`da2fa2d2fbb74945bff343c2ad3ed128c74d8e22`.

## Supported target and release

- THE IDOLM@STER STARLIT SEASON, Windows x64, game **1.61**, Steam build
  **8278842**, Unreal Engine **4.24**, Steam app **1046480**.
- Shipping executable: `StarlitSeason/Binaries/Win64/StarlitSeason-Win64-Shipping.exe`.
- Supported Shipping SHA-256:
  `881df05d33a9b25d276122f010169d790e6cee18667136983f8bef0caa6bf2c2`.
- Pinned loader archive: `UE4SS_v3.0.1-1196-g236adf26.zip` from the
  [UE4SS experimental release](https://github.com/UE4SS-RE/RE-UE4SS/releases/download/experimental-latest/UE4SS_v3.0.1-1196-g236adf26.zip).
  Its SHA-256 is
  `75dc8b081d324fe0598a87b26e37d13a84d3648cbb1d08eb48c514376407a11b`.
  The experimental URL can change; verify the hash and do not substitute a
  newer loader without compatibility testing.
- Player asset: `starlit-season-furigana-v0.1.0-alpha.2-windows-x64.zip`.
  Published ZIP SHA-256:
  `321bdfdf86bc650bf297a0d54d977e8949134690f60d58fd9df8862318f939b1`.

For a fresh installation, extract all ZIP contents next to `StarlitSeason.exe`,
run `Check-Furigana.cmd` with the game closed, then launch through Steam.
Furigana starts enabled; **F7** toggles it. The package contains 14 owned runtime
files plus five helper files. UE4SS's original MIT license is included.

## Repository map

| Path | Responsibility |
| --- | --- |
| `mod/Scripts/main.lua` | Widget discovery, exact-source stability gate, renderer lifecycle, F7 |
| `mod/Scripts/umg_ruby.lua` | UMG measurement, fonts, slot transforms, generated widgets |
| `mod/Scripts/ruby_layout.lua` | Pure Lua word/ruby layout, wrapping, punctuation, font fitting |
| `mod/Scripts/reading_lookup.lua` | Release hash/span lookup and legacy private table support |
| `mod/Scripts/sha256.lua` | Pure Lua 5.4 SHA-256 of exact UTF-8 source bytes |
| `config/` | Pinned UE4SS settings and three native signature overrides |
| `tools/extraction/` | Read-only local resource recovery, extraction, and parsing |
| `tools/readings/generate.py` | Private exact-source reading generation |
| `tools/readings/overrides.json` | Reading overrides and scoped corrections |
| `tools/readings/export_annotations.py` | Export private readings to shareable hash/span/kana data |
| `tools/install_mod.py` | Python-managed installation, ownership, backups, rollback, removal |
| `tools/build_release.py` | Deterministic portable ZIP assembly from private local inputs |
| `portable/` | Windows CMD entry points, PowerShell manager, packaged quick-start |
| `tests/`, `tools/**/test_*.py` | Synthetic source, Lua, installer, and Windows package tests |
| `docs/` | English usage, technical evidence, limitations, screenshots, release notes |

## Data flow and runtime contracts

1. Extract original Japanese CML rows and resolved character profiles locally.
   [Extraction details](docs/asset-extraction.md) describe the supported formats.
2. Generate private `readings.json` and legacy `readings.lua` using the pinned
   Sudachi dependencies. Segments must reconstruct every source exactly.
3. Export release annotations in the `starlit-furigana-spans-v1` format. Entries
   contain the exact-source SHA-256, UTF-8 byte length, and spans with 1-based
   byte positions, byte lengths, and kana readings or a `false` control marker.
   Unannotated strings are omitted; duplicate sources share one entry.
4. The runtime hashes the live widget text and reconstructs base segments from
   that text. Release data contains no original base dialogue, asset paths, or
   row identities. Legacy private exact-text tables remain supported.

Preserve these contracts when changing the runtime:

- Consider only eligible live transient conversation widgets, excluding
  templates, names, guides, and generated widgets.
- Preserve the native typewriter renderer. Apply annotations only after an
  exact source remains unchanged across successive 250 ms polls.
- Remove stale annotations when text changes. F7 must restore native opacity
  and detach generated canvases.
- Unsupported markup, unmatched substitutions, invalid spans, unsupported
  layouts, or text that cannot fit must keep the native renderer visible.
- Use the game's original font and reflected slot layout. `FGeometry` access
  returned zero sizes in this build. Supported anchors are CanvasPanelSlot or
  a single-text VerticalBox anchored in one.
- Generated widgets must remain `HitTestInvisible`. Do not replace choice
  input behavior as part of a text-rendering change.

## Installation and private-data boundaries

- Preserve original executables, base PAKs, unrelated mods, saves, and user
  configuration. Do not bypass unsupported-build checks or ownership hashes.
- Close the game before runtime installation/removal. Avoid overwriting an
  existing loader; remove the managed installation using its own workflow.
- Portable backups/state live at `.starlit-furigana-portable-state` under the
  game root. Python-managed state lives at `.starlit-furigana-state`. Keep
  these workflows separate and preserve backups until removal finishes.
- Both workflows handle the known `pakchunk99-EngPatch.pak` and `.sig` by
  backing up present files outside the PAK loading tree and restoring them on
  removal. Do not disable arbitrary mods automatically.
- Ownership and backup hashes are checked before removal. Preserve the path
  allowlist, root confinement, reparse-point checks, and rollback behavior in
  the portable manager. Logs and unrelated files must survive removal.
- Keep keys, decoded memory, extracted assets, full dialogue, resolved profiles,
  private reading tables, saves, and raw analysis dumps outside Git/release
  uploads. Use ignored `.local/` or an external private working directory.
  Do not print resource keys into logs or responses.
- Git tracks source, synthetic fixtures, and documentation. The Windows release
  additionally bundles the pinned UE4SS runtime/license and annotation-only
  data. Review publication contents explicitly; `.gitignore` is not a complete
  publication check.

## Development and verification

Run from the repository root using a virtual environment. Python **3.10** was
used for the release. Dependencies are in `requirements.txt`; development adds
`lupa==2.6` for Lua 5.4 through `requirements-dev.txt`. SudachiPy **0.6.11** and
SudachiDict-core **20241021** are deliberately pinned together.

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
& '.\.venv\Scripts\python.exe' -m unittest discover -s tools/readings -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s tools/extraction -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s tools -p test_install_mod.py -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s tools -p test_portable_release.py -v
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

The release baseline is **60 passing tests**: 11 reading, 6 extraction, 11
Python installer, 7 Windows portable, and 25 Lua lookup/layout/runtime-gate
tests. These use synthetic data without launching the game. Portable tests
require Windows; Lua tests require the development dependencies.

The private corpus contained 59,361 records from 163 CML tables and 53,567
distinct strings. All distinct strings were checked against the release lookup;
49,749 annotated entries reproduced the reference spans and controls.
Candidate coverage was 258,766 of 259,130 visible kanji (about 99.86%), with
362 unresolved records. **Zero complete records were manually reviewed.**
Coverage is not linguistic accuracy.

The exact release ZIP passed a real clean runtime install, Steam launch,
visible furigana, F7 off/on, removal with identical patch restoration hashes,
and reinstallation. The published ZIP was downloaded again and checked against
the tested artifact. See [the verification record](docs/runtime.md) and
[release notes](docs/releases/v0.1.0-alpha.2.md) for evidence.

For documentation-only changes, check links, commands, and `git diff --check`;
re-running game tests is unnecessary. For behavior changes, run affected suites
and perform the relevant in-game checks before expanding compatibility claims.

## Known limits and follow-up work

- Readings are automatic. Names, counters, context-dependent words, and formal
  pronoun variants need review. Make corrections through the documented
  [reading pipeline](docs/reading-pipeline.md), preserving exact-source scope
  where a global override would change unrelated contexts.
- Dialogue, fitted two-line text, three choice labels, and F7 were observed at
  **1680 x 1050**. A 1080p attempt clamped to that display size; true 1080p
  remains unverified.
- Album replays established choice rendering. They did not establish changed
  branches or normal-play choice input; controller input is also unverified.
- Every cinema/novel/DLC family, long sessions, all skip/auto transitions, and
  a full playthrough remain unverified. Menus, profiles, and lyrics are out of
  scope. Rich-text tags such as `<pop_G>` retain native rendering.
- The REA/Ghidra provider import failed with a sharing violation. Do not claim
  successful decompilation from that attempt; the implemented findings have
  other recorded evidence.

## Building another release

Players should continue using the published ZIP. Maintainers need private
`readings.json` and the exact pinned loader to build a new package:

```powershell
& '.\.venv\Scripts\python.exe' tools/build_release.py --loader-zip .local/ue4ss.zip --readings-json .local/generated/readings.json --output .local/starlit-season-furigana-NEW-VERSION-windows-x64.zip
```

Before using that example, set the actual new version in
`tools/build_release.py`, the portable quick-start, and release documentation;
replace `NEW-VERSION` in the output path. The packager refuses to overwrite an
existing ZIP. Keep published tags/assets immutable and use a new version for
changed runtime contents. Retain UE4SS's license.

Check package contents for private data, run the relevant suites, test the exact
ZIP through installation/removal and in-game rendering, and publish checksums.
Download the uploaded asset again to verify it matches the tested package.
Do not turn sampled visual checks into claims of full game compatibility.

## Original development machine (dated context)

The original game root was `D:\SteamLibrary\steamapps\common\StarlitSeason`;
the checkout was `.furigana-work/project` beneath it, and a sibling
`.furigana-work/.venv` supplied Python. Private extraction, evidence, reading
outputs, release artifacts, and archived logs were kept outside the checkout.
Those paths are local context, not prerequisites for a fresh clone.

At the end of the release verification the game was closed, the portable alpha.2
runtime was installed, and the known English patch was backed up and disabled.
Recheck this before operating on that machine. Do not reinstall or remove the
working runtime merely to edit source documentation.
