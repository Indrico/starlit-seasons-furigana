# Runtime behavior and verification

## Alpha.2 menu-layout correction

On 2026-11-06, the alpha.2 package was checked at a 1920 x 1080 client viewport.
The main menu's Album help banner and Enter/Esc guides retained their native
positions when comparing F7 off/on. The bottom-right gray background no longer
grew to contain the generated overlay's padding. Options System scrolling kept
ruby inside its scrolling area, and the Album character header/replay titles
retained their main fonts and annotations. The first two Haruka No.001 replay
lines and their short backlog retained body/name readings after preparation.
This did not repeat alpha.1's long-log or frame-time matrix.

The geometry-based overlay now stretches its outer slot with zero offsets;
only an inner canvas receives the absolute source bounds and scale. The source
suites contain 127 tests, including a regression for native desired-size
contributions at several scales. The package retains the same native DLL and
reading dataset. Frame-time captures were not repeated for this layout update;
the alpha.1 outliers below remain an open follow-up. This focused check does not
extend the full-game, controller, or stability coverage recorded below.
The exact ZIP passed removal/reinstallation with all 26 runtime hashes checked;
both known English-patch restoration hashes and saved preferences matched.

## Alpha.1 names, menus, and backlog verification

Version 0.3 keeps the native dialogue bridge and adds an independent lifecycle
for Japanese UI. Native menu/name glyphs remain visible with ruby-only overlays;
the base font, width, alignment, and input remain native. Menu ruby is smaller
than name/log ruby. Supported backlog bodies use the native 26-unit body font
with 14-unit minimum readings and taller selected/unselected cards. See
[UI implementation and fallbacks](ui-annotations.md).

Local checks on 2026-11-05/06 used the supported game and a 1920 x 1080 client:

- Main-menu help text and button guides, Album replay titles, full character
  names, and dialogue speaker names received readings without reducing their
  native main font. The final menu pass uses smaller readings in response to
  the player's screenshot; compact captions scale their minimum proportionally.
- Options System scrolling was checked in the final package. Ruby intersects the
  ScrollBox clip instead of floating over the footer; transform changes during
  opening animations invalidate the ruby size cache. F8 off/on restored native
  text and then annotations without changing the main font.
- Short and longer Haruka replay backlogs were opened. Native focus and voice
  replay indicators remained usable, and F7 restored original dimensions. A
  later reopen check exposed scheduling starvation and repeated work before
  a cooperative checkpoint. The final scheduler rotates existing overlays;
  completed native run updates are cached before yielding. Ordered native row
  heights and scroll offset avoid stale offscreen geometry during culling.
  Synthetic regressions cover interrupted long pages, bounded row-map rebuilds,
  newly visible sources, and keeping the bottom endpoint after row growth.
  The final package was checked with a longer log after automatic progression:
  older rows gained readings after scrolling, F7 off/on restored native sizing
  and annotations, and a close/reopen retained a fully visible last card once
  preparation settled. Deferred endpoint correction did not prevent scrolling
  upward. Native voice-control selection/indicators were observed; audio quality
  was not measured.
- Ordinary complete dialogue retains fixed 29/14 text and ruby. Manual holds,
  F6 automatic progression, return to manual, F7 off/on, and startup skipping
  were sampled. One overflowing choice retained native text because its ruby
  did not fit the existing choice rectangle at 22/11.

The final portable package has 26 owned runtime files and five helpers. Local
installation hashes and source scripts were compared with its ZIP. Real
removal/reinstallation restored both known English-patch files before disabling
them again. Preferences were preserved. The package excludes private probes,
profilers, original assets, and original base text.

There are 126 synthetic tests: 81 Lua, 17 reading, 9 extraction, 12 Python
installer, and 7 Windows portable tests. Synthetic lifecycle coverage exercises
100 sources and 30 disable/reopen cycles; this is not a claim of 100 native
backlog entries or 30 native menu reopens. The release lookup was compared with
all 62,508 distinct private source strings, including 56,494 annotated matches.
See [performance evidence](performance.md) for sampled frame intervals.

Image support is limited to direct texture brushes with calibrated bindings.
The 99 exported name-texture bindings were validated offline; this does not
establish visual verification of every image-backed label or dynamic material.
Unknown names, unresolved rich styles/markup, unmatched substitutions, and
unsupported transforms retain native rendering. Lyrics are excluded. UI cold
preparation can briefly leave native text visible. Full controller coverage,
every DLC/screen, a continuous 60-minute final-build stability run, and a full
playthrough remain unverified. The approximately 40-minute previous-candidate
session and shorter final-package checks do not establish those guarantees.

## v0.2 dialogue implementation and historical checks

The development branch uses a build-locked native bridge for message assignment,
completion waits, advance input, cleanup, and choices. It validates the Shipping
EXE hash and live instruction prefixes before installing in-memory hooks. No
executable or PAK on disk is patched. The compiled bridge completes native reveal
batches, then calls Lua synchronously to prepare the full line and annotations.
It avoids the game's skip/stop-voice handlers. See [native notes](../native/README.md)
and [controls and preferences](dialogue-controls.md).

Supported dialogue starts in manual mode. F6 changes and persists that mode;
automatic progression reads each page before releasing the native completion
wait. Fixed ordinary sizes are 29/14, cinema 30/15, and choices 22/11. Long text
is paginated rather than reduced. Ordinary windows follow the native panel width
(1280 inspected units), use 22% viewport height, and keep ruby close to its base.
F7 restores native visuals independently of the progression mode.

The OPTION menu contains a persistent master On/Off control, also accessible
through F8 while that menu is open. Off bypasses native reveal, wait, advance,
and choice modifications as well as annotations and startup skipping. Preferences
are stored outside owned runtime files at `StarlitFurigana/user-settings.ini`.
When enabled, startup advances the native logo flow to Press Any Button without
replacing the game's subsequent state transitions.

On 2026-11-04, the supported build was sampled in an actual 1920 by 1080 client:

- Complete multiline text and ruby appeared together at fixed 29/14 sizes in
  ordinary Album and normal Story dialogue. Native line events replace the old
  stability delay. This was inspected visually, without frame-by-frame capture.
- A manual Album line remained held for 58 seconds, including over 30 seconds
  after its voice ended, while character animation continued. Enter and left
  click advanced through the native handler. Synthetic and real overflow pages
  consumed advance input before the next native line.
- F6 preferences survived restart. Automatic mode advanced sampled Story and
  Album dialogue; returning to manual held the current line. A native three-choice
  Album display retained its separate plates with 22/11 annotations.
- The Options master control worked through mouse input and F8, saved the
  preference, and remained usable after more than 80 seconds. F8 outside Options
  did not toggle the setting. The checker is rooted for process lifetime because
  the native HitAreaWidget retains an unreflected pointer to it; an earlier
  unrooted prototype crashed after collection and has been removed.
- Enabled startup reached Press Any Button through the native logo-flow skip.
  After disabling the master switch in Options and restarting, the preference
  remained off and the native ILCA opening logo appeared again.
- F7 restored the native background, name decoration, cursor, and blur bounds;
  enabling it again restored the compact layout. The original blur follows the
  new window bounds, preventing a blurred strip beneath the shorter window.

The performance update replaces recurring global scans with registered objects,
uses game-thread timers and queued shortcuts, bounds font measurements, and
allocates ruby TextBlocks only when needed. Three 120-second held-line captures
reduced p99 from 59.715–60.119 ms to 6.849–6.858 ms on the local machine. A separate
automatic-progression capture also removed the recurring >50 ms spikes.
See [the performance report](performance.md) for methodology, stability findings,
and the limits of these measurements. Physical controller input, normal-play
branching choices, all cinema/novel/DLC paths, and a complete playthrough remain
unverified. A source match does not establish visual correctness for every family.

There are 93 automated tests: 57 Lua lookup/layout/runtime/controller/menu/performance tests,
12 Python installer tests, seven Windows portable tests, 11 reading tests, and
six extraction tests. They use synthetic inputs. Runtime tests establish control
flow rather than full-game compatibility, voice correctness, or crash safety.

![Master switch in Options](images/mod-options.jpg)

![Compact fixed-size dialogue at 1920 by 1080](images/compact-dialogue-1080p.jpg)

The earlier local [functional candidate](releases/v0.2.0-alpha.1-candidate.md) bundled
21 runtime files and five helpers. The final renderer was checked in-game,
including F7 restoration and a subsequent multiline native line. Its exact ZIP
then passed clean installation and runtime hash checks. Removal restored both
English-patch files with identical hashes and preserved user preferences; the
final ZIP was installed again. The Shipping EXE hash stayed unchanged. No private
inspection helpers or original game assets are included.

The optimized package adds `object_registry.lua`, bringing the runtime to 22
owned files plus five helpers. Current packaging and runtime checks are recorded
in the [v0.2.0-alpha.1 release notes](releases/v0.2.0-alpha.1.md).

The exact optimized ZIP passed clean portable preparation, a Steam launch with
the native bridge ready, complete compact furigana, a held manual line through
a 120-second frame capture, F7 native-background/blur restoration and return,
and F6 automatic progression followed by manual restoration. Its uninstrumented
held-line p99 was 6.848 ms, with a 10.625 ms maximum and no >33.33 ms intervals.
Removal restored both known English-patch files with hashes matching the saved
state; preferences also retained their hash. The same ZIP was reinstalled and
checked again. Its 27 members matched the owned manifest and source scripts;
no private profiler or extra inspection mod was installed. The supported Shipping
EXE SHA-256 remained unchanged.
After reinstallation, a second Steam launch reached Press Any Button; the Options
master button switched off through mouse input and back on through F8. Final
preferences were enabled/manual, the checker passed again, and the game was closed.

## Published alpha.2 behavior and historical verification

The remainder records the earlier published release and its 2026-11-03 tests.
The old typewriter wait, font fitting, test totals, and 1080p limitation below
apply to that version, not the current development implementation.

The runtime uses UE4SS Lua and the game's original UMG font. It adds separate
small kana TextBlocks above annotated words in eligible Japanese conversation
text. It does not modify the executable or save files.

## Source selection and native text reveal

Only live `/Engine/Transient` instances of the named dialogue, monologue,
cinema, novel-text, and selection text widgets are considered. Blueprint
templates, character name labels, control guides, and mod-generated TextBlocks
are excluded. The current widget text must exactly match a generated original
Japanese source entry that contains at least one reading.

Runtime observation confirmed that dialogue text grows as a prefix during the
native typewriter effect. The integration keeps the original renderer visible
while the text changes. Furigana is applied only when an exact matching source
remains unchanged across two successive 250 ms polls. A source-text change removes
the previous annotation and restores native rendering before the next wait.
Consequently, readings normally appear after a completed line, rather than
progressively above individual characters during the typewriter animation.

Furigana starts enabled. **F7** disables it, restores original opacity, and
detaches generated canvases. F7 enables it again. Disable furigana before
reloading Lua scripts; reloading an active renderer without first disabling it
has not been verified. Restarting the game clears runtime widgets.

## Layout

The adapter supports a direct `CanvasPanelSlot` or a text widget that is the
only child of a VerticalBox whose slot is a CanvasPanelSlot. It creates a sibling
CanvasPanel and copies the anchor slot's anchors, alignment, position, size,
render transform, and pivot. For a single-text VerticalBox, a second inner
canvas preserves the text's padding, vertical alignment, and render transform.
This avoids passing opaque `FGeometry` values
through UE4SS: that path returned zero-size geometry in the tested game build.
The observed ordinary dialogue slot is 960 by 116 local units, centered in its
parent; layout uses the actual slot values rather than hard-coding that size.

TextBlock measurement provides glyph widths and heights. Ruby is centered over
its base word; explicit line breaks, source margins, and left/center/right
justification are preserved. Annotated word groups wrap together. The layout
includes basic Japanese punctuation restrictions and treats supplementary
Unicode characters as one codepoint.

The font-fitting loop starts at the source font size and decreases by one point
until both base text and kana fit the source rectangle, stopping at 18 points
(or the original size when already smaller). Kana uses approximately 48% of the
base size, with an eight-point minimum. Generated text is clipped to that
rectangle. If readable text cannot fit, the original text remains visible.
Base text preserves the original outline; kana omits that thick outline for
legibility at small sizes. Font measurements are cached separately for base and
kana roles. Fit diagnostics include the chosen sizes, line count, required and
available heights, and measured glyph heights.
Ordinary dialogue may add up to four local units of height to accommodate pixel
rounding, keeping the original top edge and clipping enabled. Other widget
families do not receive that extra height. Explicit CR/LF units never enter font
measurement, so line breaks cannot pollute cached single-line glyph heights.

For table-backed rich text, the original `FONT-JP` font with face `Text` is
resolved explicitly. Default dialogue style uses size 29; cinema style uses 30.
These values were read from the installed original style tables. Plain
TextBlocks retain their own font and color. Generated widgets are
`HitTestInvisible`, so they do not take over choice-button input.

Other nested panel layouts and rich-text markup such as `<pop_G>` are
currently rejected without hiding the original text. Unsupported cases are
logged once per source. They must not be counted as successfully annotated.
Hidden generated canvases, unused pooled TextBlocks, and the idle measurement
TextBlock are collapsed, so they do not participate in layout.

## Standalone tests

From the repository root, install the development requirements and run:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
```

There are 18 standalone tests: ten exercise ruby positioning, justification,
Unicode, line breaks, punctuation, and stable partial-word layout; eight exercise
source selection and the exact-source stability gate. They verify that changing
text removes the old annotation, unchanged text does not repaint repeatedly,
and disabling the mod detaches generated renderers.

These tests use Lua 5.4 through `lupa==2.6`. The runtime-gate tests use a simulated
UMG adapter; they establish control-flow behavior rather than real-game
rendering, timing, input compatibility, or crash safety.

## Local visual verification

On 2026-11-03, the supported Steam build was tested in a 1680 by 1050 window:

- Main Story replay dialogue displayed kana above kanji using the original font.
- Haruka's first Kizuna replay displayed one-line and fitted two-line dialogue.
- All three answer labels displayed aligned kana inside their original choice plates.
- Native typewriter text remained visible during reveal. Successive lines and scene changes removed the previous annotation during the observed replays.
- F7 restored native text and enabled annotation again. The game then closed normally with Alt+F4.
- After a clean managed installation, Steam launch and the same dialogue/choice rendering worked without the development probe or bundled sample mods.

![Two-line dialogue with furigana](images/dialogue.jpg)

![Three native answer choices with furigana](images/choices.jpg)

The Album replay showed a zero timer and a highlighted right-hand answer. A
keyboard and a mouse attempt did not demonstrate a changed branch, so these
replays establish choice rendering but do not certify interactive choice input.
The generated canvases use `HitTestInvisible`; a normal-play input test remains
open.

These are sampled checks, not a complete playthrough. Interactive choice and
controller input, every conversation family (cinema/novel/DLC), every choice layout, prolonged sessions,
and every skip/auto-advance transition still require broader testing. A source
match or log message alone does not establish correct visual rendering.

A separate 1920 by 1080 launch was attempted through Steam arguments and a
temporary game configuration. The game clamped its window back to 1680 by 1050
on this display; therefore a true 1080p visual result is not claimed.

## Drag-and-drop release verification

For `v0.1.0-alpha.2`, the old managed loader was removed and the exact Windows
release ZIP was extracted into the clean runtime directory. The included
checker verified all 14 runtime files and backed up both known English-patch
files. Steam startup and dialogue rendering succeeded with the bundled loader
and the prebuilt hash/span annotation table, without the private exact-text
reading database. F7 disabled and re-enabled annotations. After normal game
exit, the bundled uninstaller removed the owned runtime files and restored both
English-patch backups with identical hashes. The same ZIP was reinstalled and
checked successfully for the final local setup.

![Dialogue rendered using the drag-and-drop package](images/portable-dialogue.jpg)

The release lookup was also run against every one of the 53,567 distinct local
source strings. All 49,749 annotated entries reproduced the original base text,
reading spans, and control markers; unannotated strings remained unmatched.
Seven new standalone tests cover SHA-256, Unicode byte spans, source mismatch,
and payload validation. Seven Windows package tests cover fresh setup/removal,
patch restoration, edited files, unsupported builds, manifest restrictions, and
rollback when a loader cannot be renamed. Together with the existing suites,
the project has 60 passing tests.
