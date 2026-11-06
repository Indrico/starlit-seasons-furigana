# Agent guide

This is the handoff and working guide for AI agents contributing to Starlit
Season Furigana. The status below was updated on **2026-11-06**. Recheck Git,
release metadata, and the local installation before treating that status as
current. Keep repository documentation, release notes, and usage instructions
in **English**.

## Current development milestone

The current milestone is **v0.3.0-alpha.3**, reducing UI preparation delays
and suspending furigana work during MV/live performances. Names, menus, and
backlog were introduced in alpha.1. Check the actual
GitHub tag and release assets before assuming publication succeeded.
Read [UI annotations](docs/ui-annotations.md) before editing the new lifecycle.

Alpha.3 reduces delayed UI readings. Nonwrapping overlays measure span boundaries,
UI font metrics share a 4,096-entry bounded cache, and plain log runs merge only
when their measured width agrees. Per-role measurement widgets retain fonts.
Native text/line callbacks try immediate preparation; callbacks and the UI tick
share a cooperative six-millisecond budget per 16 ms window. A callback can use
at most four milliseconds. This is not a hard bound on one native operation.
Prepare during an inherited CanvasPanel fade without bypassing a source's own
hidden state. New screens/entries receive priority; pending work skips the old
50 ms poll. Native geometry still determines when a new layout can be positioned.

During MV/live, `performance_guard.lua` detects a live `LiveManager` from one
initial snapshot and queued construction notifications. Poll its cached object
set at most every 250 ms (native line events may force an early check). Suspend
UI discovery, lookups, geometry, rendering, and dialogue discovery; detach
overlays once. Preserve master/F7/manual preferences. Resume after the manager
expires. Registry notifications may still queue object references while paused.
Do not replace this with recurring global scans or music-playback detection.

Alpha.2 fixes the generated overlays inflating native auto-sized menu panels.
Geometry-based text and image overlays use an outer CanvasPanel with stretched
anchors and zero offsets; absolute bounds, padding, and scale live on its inner
canvas. Keep the outer slot free of a desired-size contribution. A fixed-anchor
padded host enlarged the footer background and shifted Enter/Esc to the left.

- Native menu/name glyphs remain visible; ruby is a sibling overlay. Menus use
  ordinary minimum 11 (7-10 for compact captions) / ratio 0.4 following the user's smaller-menu request. Names and
  backlog retain minimum 14. Never reduce the game's main UI font to fit ruby.
- UI geometry uses build-locked native FGeometry scalar copies. Padded overlays
  may escape decorative clips but must intersect ScrollBox clips.
- `ui_annotations.lua` owns discovery, independent UI scheduling, exact-name
  checks, bounded lookups, and master/F7 restoration. `backlog.lua` owns native
  row sizing/restoration and visible-plus-one-row culling. Dialogue controls
  and their accepted sizes remain separate.
- Backlog plates are stretch-anchored. Grow the two parent GridPanel canvas
  slots together; preserve plate/icon/hit-area offsets. Save numeric slot
  values, not live struct views, for restoration.
- Log culling uses ordered native desired heights/padding and scroll offset;
  offscreen cached geometry can retain its last painted position. Rebuild at
  most eight rows per frame, preserve overlays during that rebuild, and keep
  the endpoint pinned only if the user was already at the bottom.
- Cooperative preparation must cache completed run updates before yielding.
  Repeating native visibility setters on every retry can prevent a long row
  from ever finishing. Keep the interruption/progress regression test.
- Discovery is incremental and live notifications outrank the initial backlog.
  Never use Lua coroutines for reflected calls with the pinned loader; its
  unregistered coroutine states fail. UI preparation checkpoints cache results
  on the registered game-thread state with a cooperative QPC budget.
- New offline inputs combine Japanese LocRes with verified exact-name aliases;
  `texture_geometry.py` exports only normalized hashed ink bounds. Release builds
  must pass the generated `--ui-bindings`; the source fallback is empty.
- The final local installation is portable-managed at
  `.starlit-furigana-portable-state`. The final package excludes private probes
  and temporary UI samplers. Inspect the live ownership state before changing it.

`main` contains the v0.3 UI extension and the v0.2 dialogue/performance changes.
The player prerelease is **v0.3.0-alpha.3**; verify its GitHub metadata and asset
checksum before installation. Do not overwrite historical release assets.
The user's local `plan.md` is intentionally untracked.

- Default manual dialogue; F6 switches manual/automatic progression and persists
  the preference. Native advance input consumes pages before forwarding a final
  advance to the game. Voice playback and animation stay independent.
- Complete text and furigana are prepared synchronously at native line events.
  Fixed ordinary sizes are 29/14, cinema 30/15, and choices 22/11. The legacy
  250 ms stability gate/font fitting is only a bridge-unavailable fallback.
- The user accepted the font sizes, then requested a shorter and narrower box
  and closer ruby. Use the native panel width (1280 inspected units), compact
  22% viewport height, and metric gap -12. Paginate instead of shrinking.
- OPTION contains a master On/Off button; F8 in that menu is its keyboard
  equivalent. Off bypasses every mod feature, including native text completion,
  manual progression, and startup skipping. Keep the menu available while off.
- Enabled startup skips the native logo flow to Press Any Button. Preserve the
  game's subsequent first-run/license checks and startup state transitions.
- Writable preferences are `StarlitFurigana/user-settings.ini` under the game
  root: `enabled`, `manual`, `auto_min_seconds`, `auto_characters_per_second`.
  Preserve them during uninstall and keep them outside owned-file hashes.
- Performance work replaces recurring discovery with one initial class
  snapshot plus construction notifications; native lines resolve registered
  owners directly. Timers run on the game thread, input queues commands, and
  each renderer bounds measurement state. Read [performance evidence](docs/performance.md)
  before making timing claims. Earlier profiling exposed callback-reference
  crashes in an async scheduling pattern, also present in the old baseline.

Read [dialogue controls](docs/dialogue-controls.md), [native bridge notes](native/README.md),
and the current section of [runtime verification](docs/runtime.md) first.

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
- Added a build-locked native bridge, manual/auto state, fixed-size pagination,
  persistent master control, compact ruby layout, and startup-logo skipping.
- Added independent UI discovery, native-geometry ruby overlays, exact character
  aliases, calibrated image bindings, and reversible backlog card sizing. Menu
  readings are smaller than name/backlog readings. Cold UI preparation is
  cooperative; active overlays rotate without starving newly visible sources.
- Published **[v0.2.0-alpha.1](https://github.com/Indrico/starlit-seasons-furigana/releases/tag/v0.2.0-alpha.1)**
  with the native bridge, compact fixed-size layout, persistent controls, startup
  skipping, and measured performance improvements. Older releases remain
  available historically.

Implementation history:

| Commit | Result |
| --- | --- |
| `08599b8` | Initial dialogue/choice mod, extraction, readings, installer, and tests |
| `b1bae42` | First alpha release documentation and English usage guide |
| `da2fa2d` | Tested drag-and-drop Windows package and annotation-only lookup |
| `f013ad5` | Functional v0.2 compact dialogue, controls, and startup implementation |

The public repository is
`https://github.com/Indrico/starlit-seasons-furigana.git`, with development on
`main`. Read the current tag on GitHub; historical `v0.1.0-alpha.2` points to
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
- Player asset: `starlit-season-furigana-v0.3.0-alpha.3-windows-x64.zip`.
  ZIP SHA-256:
  `7709f5de8639760f11b548a4c129af83339826226c3586e6a61ed0d8940150d1`.

Extract all ZIP contents next to `StarlitSeason.exe`,
run `Check-Furigana.cmd` with the game closed, then launch through Steam.
Furigana starts enabled and dialogue is manual; F6 changes progression and F7
toggles annotations. OPTION contains the master switch (F8 while open).
The package contains 27 owned runtime files and five helpers, including the
precompiled bridge, UE4SS's MIT license, and MinHook's license. Uninstall the old
managed version before an upgrade; preserve preferences.

## Repository map

| Path | Responsibility |
| --- | --- |
| `mod/Scripts/main.lua` | Native events, discovery/fallback, lifecycle, F6/F7/F8, master switch |
| `mod/Scripts/object_registry.lua` | One initial class scan, queued construction notifications, expired-object cleanup |
| `mod/Scripts/performance_guard.lua` | MV/live lifecycle gate; cached object checks, no recurring global scans |
| `mod/Scripts/ui_annotations.lua` | Independent menu/name/log lifecycle, budgets, bounded lookup, restoration |
| `mod/Scripts/ui_geometry.lua` | Cached native geometry and supported relative transforms |
| `mod/Scripts/backlog.lua` | Native log culling, shared selected/unselected row sizes, numeric restoration ledger |
| `mod/Scripts/ui_bindings.lua` | Empty source fallback; package uses private generated hash/kana bindings |
| `mod/Scripts/dialogue_controller.lua` | Manual/auto state, page input and reading timers |
| `mod/Scripts/settings.lua` | Non-executable preferences outside protected runtime files |
| `mod/Scripts/mod_menu.lua`, `startup.lua` | Native Options control and logo-flow skipping |
| `mod/Scripts/native_bridge.lua`, `native/bridge.cpp` | Build-locked in-memory hooks and UE4SS C-export bridge |
| `mod/Scripts/umg_ruby.lua` | UMG measurement, fonts, slot transforms, generated widgets |
| `mod/Scripts/ruby_layout.lua` | Pure Lua word/ruby layout, wrapping, punctuation, font fitting |
| `mod/Scripts/reading_lookup.lua` | Release hash/span lookup and legacy private table support |
| `mod/Scripts/sha256.lua` | Pure Lua 5.4 SHA-256 of exact UTF-8 source bytes |
| `config/` | Pinned UE4SS settings and three native signature overrides |
| `tools/extraction/` | Read-only local resource recovery, extraction, and parsing |
| `tools/readings/generate.py` | Private exact-source reading generation |
| `tools/readings/build_ui.py` | Combine Japanese localization, dialogue, and exact verified name aliases |
| `tools/extraction/texture_geometry.py` | Private inline name-texture decode; export hashed normalized bounds only |
| `tools/readings/overrides.json` | Reading overrides and scoped corrections |
| `tools/readings/export_annotations.py` | Export private readings to shareable hash/span/kana data |
| `tools/install_mod.py` | Python-managed installation, ownership, backups, rollback, removal |
| `tools/build_release.py` | Deterministic portable ZIP assembly from private local inputs |
| `tools/summarize_frametimes.py` | Aggregate PresentMon v1 frame intervals without raw process records |
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

- Dialogue discovery handles its conversation families; the independent UI
  lifecycle handles eligible transient names, guides, menus, and log widgets.
  Always exclude generated widgets and lyrics. Avoid annotating the same source
  through both lifecycles.
- With the supported native bridge, complete native reveal and prepare the
  final ruby layout in the assignment callback before returning to the game.
  Never invoke skip/stop-voice functions to complete text. Newline/control units
  reset native elapsed time, so one reveal call can leave a truncated source.
- Use fixed family font sizes and paginate overflow. Preserve kana-only line
  spacing. The bridge-unavailable fallback retains the old typewriter and
  successive-250-ms-poll gate.
- The original BackgroundBlur is a separate child of `message_window`. Move its
  CanvasPanelSlot to the resized window with the native ten-unit inset, and
  restore all original anchors/alignment/offsets on hide. Hiding only background
  images leaves a blurred strip beneath the compact window.
- Remove stale annotations when text changes. F7 must restore native opacity
  and detach generated canvases.
- Unsupported markup, unmatched substitutions, invalid spans, unsupported
  layouts, or text that cannot fit must keep the native renderer visible.
- Use the game's original font. Dialogue supports CanvasPanelSlot or a
  single-text VerticalBox anchored in one. Reflected `FGeometry` marshals as
  zeroes in this loader; UI overlays use the pinned native scalar-copy bridge,
  preserving native widths and transforms. Unsupported geometry stays native.
- Generated widgets must remain `HitTestInvisible`. Do not replace choice
  input behavior as part of a text-rendering change.
- The Options toggle intentionally accepts input. `HitAreaWidget` must be
  registered with a live `HitAreaChecker` before it can signal clicks. Its raw
  checker pointer is not reflected: root exactly one process-lifetime checker
  with `RF_MarkAsRootSet` (0x80), using GameInstance as outer. An unrooted
  checker caused a confirmed development crash after GC. Do not use async
  loading flags to keep it alive; they stalled startup in this build.

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

The current suites contain **147 tests**: 17 reading, 9 extraction, 12
Python installer, 7 Windows portable, and 102 Lua lookup/layout/runtime/controller/menu/performance
tests. These use synthetic data without launching the game. Portable tests
require Windows; Lua tests require the development dependencies.

The combined private corpus contains 71,309 records and 62,508 distinct strings,
including dialogue from 163 CML tables. All distinct strings were checked against
the package lookup; 56,494 annotated entries reproduced the reference spans and
controls. Candidate coverage is 294,980 of 295,416 visible kanji, with 467
unresolved records. **Zero complete records were manually reviewed.**
Coverage is not linguistic accuracy.

The exact release ZIP passed a real clean runtime install, Steam launch,
visible furigana, F7 off/on, removal with identical patch restoration hashes,
and reinstallation. Verify the published download against the checksum above.
See [the verification record](docs/runtime.md) and
[release notes](docs/releases/v0.3.0-alpha.3.md) for evidence.

For documentation-only changes, check links, commands, and `git diff --check`;
re-running game tests is unnecessary. For behavior changes, run affected suites
and perform the relevant in-game checks before expanding compatibility claims.

## Known limits and follow-up work

- Alpha.3's exploratory MV sample still has frame spikes while furigana work is
  suspended (p99 37.854 ms; 141 intervals above 33.33 ms in 60 seconds). An
  unsynchronized pre-suspension sample has better p99 but a larger maximum.
  Do not claim an overall FPS improvement. Retain both captures and use matched
  song/camera phases plus CPU/GPU attribution for further diagnosis.
- Ready-text preparation is faster, but cold menu geometry/admission can still
  cause ruby pop-in. The request for immediate readings everywhere remains open.
- The late v0.3 candidate held-line matrix has one run with nine intervals above 33.33 ms
  (maximum 815.323 ms); two other runs have none. There is no same-session paired
  baseline or CPU attribution. Treat occasional stuttering as an open follow-up,
  preserve all samples, and do not substitute clean captures for the outliers.
- Readings are automatic. Names, counters, context-dependent words, and formal
  pronoun variants need review. Make corrections through the documented
  [reading pipeline](docs/reading-pipeline.md), preserving exact-source scope
  where a global override would change unrelated contexts.
- Dialogue, fitted two-line text, three choice labels, and F7 were observed at
  **1680 x 1050** for alpha.2. The v0.2 work also runs at an actual
  **1920 x 1080 client viewport**; check the current runtime record for its scope.
- Album replays established choice rendering. They did not establish changed
  branches or normal-play choice input; controller input is also unverified.
- Every cinema/novel/DLC family, every menu/profile screen, long stability runs,
  all skip/auto transitions, and a full playthrough remain unverified.
  Lyrics are out of scope. Rich-text tags such as `<pop_G>`, unresolved rich
  styles, unknown names, and unbound image/material labels retain native rendering.
- The REA/Ghidra provider import failed with a sharing violation. Do not claim
  successful decompilation from that attempt; the implemented findings have
  other recorded evidence.

## Building another release

Players should continue using the published ZIP. Maintainers need private
`readings.json` and the exact pinned loader to build a new package:

```powershell
& '.\.venv\Scripts\python.exe' tools/build_native.py --output .local/build/StarlitFuriganaNative.dll
& '.\.venv\Scripts\python.exe' tools/build_release.py --loader-zip .local/ue4ss.zip --readings-json .local/ui-generated/readings.json --native-dll .local/build/StarlitFuriganaNative.dll --ui-bindings .local/ui-generated/ui-bindings.lua --output .local/starlit-season-furigana-NEW-VERSION-windows-x64.zip
```

Before using that example, set the actual new version in
`tools/build_release.py`, the portable quick-start, and release documentation;
replace `NEW-VERSION` in the output path. The packager refuses to overwrite an
existing ZIP. Keep published tags/assets immutable and use a new version for
changed runtime contents. Retain UE4SS's and MinHook's licenses. Players must
receive the compiled DLL; they must not need MSVC or the Windows SDK.

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

During v0.2 development, Python-managed test installations replaced the older
portable runtime. The final functional candidate was installed through its
portable ZIP again. Check the actual state/ownership manifests before operating
on this machine. The known English patch is backed up and disabled while the
mod is installed. Do not reinstall or remove a working runtime merely to edit
source documentation. Keep private test probes out of the final player package.

The v0.3 player ZIP is in the sibling
`releases/v0.3.0-alpha.3-candidate7/` directory, with the checksum above.
The historical optimized v0.2 ZIP is in `releases/v0.2.0-alpha.1-optimized/`. The
`v0.2.0-alpha.1-final` folder and candidate record describe an earlier functional
checkpoint, not the optimized release. Private profiling ZIPs must never be
published. The final installation is portable-managed, enabled, and manual;
inspect live state before operating. The game is closed after verification.
