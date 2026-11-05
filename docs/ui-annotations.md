# Names, menus, and backlog

Version 0.3 adds an independent annotation lifecycle for Japanese UI.
Menu labels and character names retain the game's original text, font size,
width, justification, focus, and input handlers. A ruby-only sibling follows the
native cached geometry, including nested Grid/ScaleBox controls. The dialogue
controller still owns dialogue reveal, pagination, and manual/auto progression.
Padded ruby may cross decorative label clips, but always intersects a native
ScrollBox clip. Otherwise readings from offscreen menu rows would float above
the screen's footer.

Since alpha.2, geometry-based text and image overlays use a stretched outer
CanvasPanel with zero slot offsets. This contributes no size to the native
CanvasPanel's desired-size calculation. An inner canvas holds the source's
absolute geometry, ruby padding, and render scale. Keep those bounds off the
outer slot: otherwise native auto-sized control-guide panels grow and move
Enter/Esc when annotations appear. Scroll clipping remains on the inner canvas.

The user requested smaller menu readings after inspecting the first candidate.
Ordinary menu captions use an 11-unit minimum and a 0.4 base-font ratio. Small
native captions use a proportional 7–10-unit minimum to avoid oversized
readings on compact tags and button guides. Adjacent kanji compounds share one
reading lane rather than overlapping individually centered labels. Person names and log
messages retain the 14-unit minimum. Geometry scale compensation prevents a
ScaleBox from reducing the minimum below its viewport-relative size. Ordinary
dialogue remains 29/14; cinema and choices keep their existing family sizes.

## Reading inputs

`tools/readings/build_ui.py` merges the private CML corpus, original Japanese
LocRes entries, resolved character profiles, and exact-name aliases. Short
names are exact-source overrides; a one-character name never rewrites unrelated
words. Conflicting aliases are omitted. Unknown/player-defined names keep their
native rendering.

The local dataset contains 35 verified character identities and 160 exact-name
aliases. The combined corpus has 62,508 distinct strings and 56,494 annotated
entries. Candidate kanji coverage is 294,980 / 295,416, with 467 records containing
unresolved cases. Zero complete records have been manually reviewed. Coverage
does not establish linguistic accuracy.

Release `readings.lua` contains hashes, byte spans, and kana. Generated
`ui_bindings.lua` contains hashed exact-name/texture identities and kana; optional
normalized `left`, `right`, and `top` coordinates locate an image's ink. No base
text, original texture, asset path, profile row, or resource key is distributed.
The checked-in bindings file is an empty development fallback, not release data.

```powershell
python tools/readings/build_ui.py --dialogue .local/corpus/dialogue.jsonl --localization .local/localization-ja.json --profiles .local/character-profiles-resolved.json --image-geometry .local/ui-image-geometry.json --output .local/ui-generated
python tools/readings/export_annotations.py .local/ui-generated/readings.json --output .local/ui-generated/annotations.lua
```

`--image-geometry` is optional. It accepts a JSON object keyed by SHA-256 of the
lowercase texture basename, with normalized ink bounds. When supplied, only
calibrated texture identities enter the binding export. This candidate locally
calibrates 99 known name textures using BC7 or BGRA inline mips. It does not
perform OCR or patch texture assets. Rebuild normalized geometry locally with
the development dependencies installed:

```powershell
python tools/extraction/texture_geometry.py --game "D:/path/to/StarlitSeason" --key-file .local/evidence/pak-key.hex --output .local/ui-image-geometry.json
```

## Backlog layout and lifecycle

The native log's selected/unselected Default/Mini panels remain in their
original order. Text replacements use the native body font size. Their two
GridPanel containers receive the same extra height, reserving 16 units above
names and messages and enough height for wrapped ruby. Stretch-anchored plates,
voice controls, and hit areas then follow their native containers. Changing
bottom offsets on those plates would shrink them; do not treat a stretched
CanvasPanelSlot's offsets as its measured height.

Only visible cards plus one card above/below the ScrollBox receive generated
text. Culling uses native desired heights, slot padding, and scroll offset;
offscreen cached geometry can retain an old painted position. The ordered row
map rebuilds at most eight children per frame when row heights/count change.
Leaving that range detaches the overlay while retaining the row's measured
height, so scrolling does not repeatedly collapse cards. F7/master Off restores
native text opacity and every saved position/size. Expired rows release their
ledger entries. Height changes keep the endpoint visible only when the user
was already at the bottom. Voice IDs, native click handlers, and selection remain native.

## Work scheduling

Text and image discovery each use an initial snapshot followed by construction
notifications. New notifications take priority over the initial backlog. There
are no periodic global widget scans. Root visibility is shared between labels;
hidden screens skip text lookup. Negative/positive reading lookup is limited to
2,048 entries; each renderer's font measurements remain bounded as before.

The UI timer has a cooperative two-millisecond wall-time budget. Existing
overlays rotate within the first millisecond, leaving time for newly visible
sources instead of repeatedly inspecting the same prefix. Identity checks follow
the same polling interval. Cold font
measurements and generated runs checkpoint into reusable caches; an unfinished
layout retries from those caches on the next tick. Completed native run updates,
including visibility, are cached before yielding so a long page cannot restart
the same prefix forever. The original text remains
visible until preparation succeeds. A reflected/native operation can exceed
the cooperative budget; this is not a hard real-time guarantee.

Do not implement this with Lua coroutines: the pinned UE4SS build associates
reflected calls with registered Lua states and rejects calls from a new
coroutine state. All Unreal operations run on its original game-thread state.
`sf_clock` uses QueryPerformanceCounter because `os.clock` counts process CPU
time across game threads. See [native notes](../native/README.md).

## Limits

Exact-source misses, substitutions, rich-text markup or unresolved table-backed
rich styles, unknown names, missing
geometry, and rotated/sheared controls retain native rendering. Lyrics remain
excluded. Generic menu support does not establish that every menu or DLC panel
has been visually verified. Newly opened UI may show its native text briefly
while geometry and annotations become ready; its main font does not shrink.
See [runtime verification](runtime.md) for the sampled surfaces and remaining
release checks.
