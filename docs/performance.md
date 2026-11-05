# Performance investigation

## v0.3 name/menu/backlog package

The late v0.3.0-alpha.1 candidate before the final deferred backlog-end adjustment
was installed without a private probe or inspection mod. The same local
1920 x 1080 Haruka Kizuna No.001 first held line
was measured three times for 120 seconds, using the PresentMon method below.

| Run | Frames | p95 (ms) | p99 (ms) | Maximum (ms) | Frames >50 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 19,773 | 6.858 | 7.197 | 11.090 | 0 |
| 2 | 19,531 | 6.851 | 7.248 | 815.323 | 7 |
| 3 | 19,774 | 6.784 | 7.184 | 8.112 | 0 |

Runs 1 and 3 had no intervals above 33.33 ms. Run 2 had nine, including seven
above 50 ms, mostly clustered around 74-78 seconds. The cause was not attributed
by this capture. These outliers remain a performance follow-up; p99 alone must
not be used to describe the build as stutter-free. The v0.2 exact-ZIP reference
from 2026-11-04 had p99 6.848 ms and maximum 10.625 ms in that scene. There
is no new same-session paired baseline, so these measurements cannot establish
whether the outliers came from the mod, the game, or other system activity.

The final ZIP changes only when the backlog-end correction is requested after
row growth; the held-line matrix was not repeated for that change. Final-package
functional checks are recorded separately in [runtime verification](runtime.md).

A separate 120-second automatic-progression capture of the final ZIP in the same replay recorded
19,773 intervals, p95 6.740 ms, p99 7.151 ms and maximum 11.014 ms, with zero
intervals above 33.33/50 ms. Manual progression was restored afterward. An earlier
candidate's automatic capture contained one unattributed 115.130 ms interval;
clean samples do not remove the open performance limitation.

UI discovery is incremental, text/image admissions are separate, and live
notifications outrank an unfinished initial snapshot. Existing overlays have
rotating priority within half the budget during focus/scroll changes, leaving
time for newly visible sources; root visibility is shared and inactive
screens skip text lookup. Negative and positive reading lookups are bounded.
Native font prepasses and generated runs checkpoint their cached work on the
registered game-thread Lua state. The two-millisecond QPC budget is cooperative;
one native operation can exceed it. It must not be described as a hard limit.

The detailed v0.2 investigation and measurements follow for historical context.

## v0.2 dialogue optimization

The performance work targets repeated game-thread discovery and dialogue
preparation in v0.2. It preserves the accepted font sizes and compact window.

## Changes

- Each relevant class has one initial object snapshot and one
  [UE4SS construction notification](https://docs.ue4ss.com/dev/lua-api/global-functions/notifyonnewobject.html).
  Notifications queue objects until the game thread can inspect initialized
  fields. Expired or renamed objects are removed, including reused addresses.
  Native dialogue events resolve the registered owner by address and register
  its exact text widget directly. If an assignment precedes notification
  delivery, a bounded owner-class recovery scan handles that miss.
- Options, logo handling, native dialogue, and idle ticks no longer repeatedly
  call `FindAllOf`. The 250 ms tick handles registered widgets, menu input,
  geometry changes, and the bridge-unavailable typewriter fallback.
- A single `LoopInGameThreadWithDelay` timer replaces async callbacks that
  repeatedly scheduled work onto the game thread. Input callbacks queue commands
  for that timer, and native bridge initialization uses a direct game-thread
  delay. This avoids repeated cross-thread creation of Lua callback references.
  Testing exposed invalid-reference errors and a crash stack also present in
  the old comparison runtime. An [upstream report](https://github.com/UE4SS-RE/RE-UE4SS/issues/1180)
  describes the matching scheduling hazard. The timer API was checked against
  [the pinned loader's source](https://github.com/UE4SS-RE/RE-UE4SS/blob/236adf26/UE4SS/src/Mod/LuaMod.cpp).
- Native events read and look up each changed complete line; idle native ticks
  reuse that text. Geometry includes the expanded viewport-dependent size.
- Font measurement prepasses only its measurement TextBlock. It no longer
  prepasses every generated child for each new measured string.
- Each renderer keeps at most 2,048 cached widths, separated by base/ruby role
  and size. Font and style belong to that renderer; a DPI scale change clears
  measurements. Layout state is limited to the current line/pages. Plain runs
  allocate a base TextBlock; a ruby TextBlock is created only when needed.
- Generated-widget bookkeeping uses weak values, so it does not accumulate
  names of expired widgets. Routine discovery/matched-line logs are disabled;
  startup, controls, and failures remain visible in the log.

## Measurement method

Local measurements use game 1.61 / Steam build 8278842, an actual 1920 x 1080
window, Ryzen 7 6800H, and RTX 3070 Laptop GPU. Graphics settings stay unchanged.
The stable scene is the first held line of Haruka Kizuna No.001 in Album.
Three independent 120-second captures sample that unchanged-text interval.
Automatic progression is measured separately with the normal 3-second minimum
and 8 characters/second preferences. Loading and menu navigation are excluded
from the held-line captures.

[PresentMon 2.6.0](https://github.com/GameTechDev/PresentMon/releases/tag/v2.6.0)
records `--v1_metrics` with `--process_id`, `--timed 120`,
`--terminate_after_timed`, `--no_console_stats`, and `--no_track_input`.
The reported metric is `msBetweenPresents`, the interval between application
Present calls, rather than display latency. Percentiles use nearest ranks.
Use `python tools/summarize_frametimes.py capture1.csv capture2.csv` to reproduce
the aggregate calculations. Raw captures and private instrumentation remain
outside Git and player packages.

A separate private Lua probe times discovery, lookup, font measurement, layout,
widget construction, attachment, and native line callbacks using `os.clock`.
Its millisecond resolution makes tiny operations appear as zero; nested costs
must not be added together. It also observes Lua heap and live renderer/pool
counts. The probe does not record original dialogue. Comparative profiled
sessions use the same probe overhead; final package checks exclude it.

## Results

The first comparison used the functional v0.2 implementation at `f013ad5` and
the optimized candidate. All six held-line captures lasted 120 seconds:

| Build / run | Frames | p95 (ms) | p99 (ms) | Maximum (ms) | Frames >50 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Functional v0.2 / 1 | 15,238 | 8.079 | 59.715 | 391.290 | 470 |
| Functional v0.2 / 2 | 15,184 | 8.111 | 60.119 | 369.484 | 469 |
| Functional v0.2 / 3 | 15,167 | 8.104 | 59.744 | 361.850 | 471 |
| Optimized / 1 | 19,776 | 6.508 | 6.850 | 14.837 | 0 |
| Optimized / 2 | 19,775 | 6.489 | 6.849 | 10.886 | 0 |
| Optimized / 3 | 19,773 | 6.501 | 6.858 | 8.084 | 0 |

A separate 120-second automatic-progression capture in the same replay gave
p95/p99 of 8.053/60.585 ms before optimization and 6.492/6.864 ms afterward.
Frames above 50 ms fell from 481 to zero. This window includes the initial held
line and subsequent native transitions, rather than 30 transitions per capture;
it does not satisfy that broader planned sample-count requirement.

The old probe measured approximately 25–30 ms for each menu/logo `FindAllOf`
call, with both repeated four times per second. The roughly four >50 ms frames
per second match that cadence. The optimized probe observed exactly one scan
per registered class through the held interval. The first native line callback
fell from 201 ms to 37 ms; initial attachment and cold font work still have a
cost. It constructed 21 objects rather than 27 for that line. The generated
text pool remained at 16 widgets and the width cache at 18 entries while held.

Early profiling also exposed invalid callback references and two matching
crashes, including one in the old runtime before the new object notifications
existed. Those early sessions are diagnostic evidence, not a stability result.
The optimized runs use game-thread timers and load the private probe directly
at mod initialization. Final player-package checks must also run without the
probe. These measurements concern one local scene and cannot establish a
guaranteed frame rate, full-game compatibility, or completion of the wider
planned loader-only/scene-transition acceptance matrix.

The revised-timer profiled session lasted more than 38 minutes without another
callback-reference error or crash. It included a complete 31-line Album replay,
a second replay with manual/auto and skip activity, F7 restoration, and the
Options master switch through mouse and F8. This is a sampled session, not
certification of every skip or choice path. A 30-minute sampler collected 61
memory snapshots: observed Lua heap ranged from 61.7 to 115.6 MiB and ended at
94.0 MiB after collection and scene changes. Held-line pool/cache counts stayed
constant; they reached zero after replay teardown. Scene loading and the probe
also allocate memory, so this does not establish leak freedom.

The exact final player ZIP was then installed with no private probe or inspection
mod. A further 120-second capture of the same held line recorded 19,774 frames:
p95 6.503 ms, p99 6.848 ms, maximum 10.625 ms, and zero intervals above 33.33 ms
or 50 ms. The line remained held throughout. This confirms the recurring-stall
result also applies to the uninstrumented package.
