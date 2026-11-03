# Reverse-engineering notes

The selected target is the user's normally installed Steam build `8278842`, game
version 1.61, Unreal Engine 4.24. Original executables and base PAK files are
preserved. No activation bypass or modified executable is part of this mod.

## Resource and text path

The original PAK files use legacy version-8 encrypted directory indexes and
Zlib-compressed members. Candidate resource keys are accepted only after the
decrypted directory passes its embedded SHA1 check. The recovery tool reads the
normally running Shipping executable's `.text` with read-only process access.

Japanese conversation strings are stored in tagged `Japanese` string properties
of CML DataTables under `Commu/Localize`. They are distinct from the UI LocRes
resources. The local English patch replaces CML tables and Japanese localization
resources, so it must be disabled when testing original Japanese text.

Ordinary messages use `RichTextBlock_Message` and `RichTextBlock_Monologue` in
`WBP_Commu_Message`. Answer choices use plain TextBlocks in `WBP_Commu_Select`;
a rich-text-only decorator would therefore miss choices. Runtime widgets expose
growing text prefixes during the native typewriter animation.

The corpus contains 41 `<pop_G>` opening tags across 33 rows, concentrated in
tutorial, unlock, acquisition, and game-over advice families. These are not
evidence of general ruby support. Unsupported styled text keeps its native
renderer rather than displaying literal tags or dropping styles.

## Loader compatibility

The pinned UE4SS build requires these verified function-start signatures:

| Signature | RVA in the supported build | Identification |
| --- | --- | --- |
| FName constructor | `0x16030f0` | Native `Conv_StringToName` wrapper passes UTF-16 text and calls this constructor. |
| ConsoleManager getter | `0x1507b20` | Singleton getter; the other default match is a reflected console-variable wrapper that calls it. |
| GameEngine tick | `0x28514e0` | UE4SS engine-tick scan, also required for custom constructor verification. |

Each supplied byte pattern matched once in the normally decoded module. The
installer checks the complete original Shipping EXE hash before using them.
Name conversion uses UE4SS's `Conv_NameToString` method because its default
ToString match did not pass the constructor confirmation on this target.

## Investigation tools

The investigation followed [REA's evidence-oriented workflow](https://github.com/morluto/rea).
REA 5.0.0 was installed locally with Ghidra 12.1.4; the Windows provider attempt
failed to import its temporary copy because of a file-sharing violation. That
attempt is not claimed as a successful decompilation. Resource parsing,
independent [repak](https://github.com/trumank/repak) comparison, decoded native
instruction inspection, UE4SS reflection dumps, and live game observation supplied
the implemented findings.

See [UE4SS's signature override guide](https://docs.ue4ss.com/dev/guides/fixing-compatibility-problems.html)
for the small Lua signature interfaces. Private resource keys, memory images,
extracted assets, complete dialogue, and raw reflection dumps are intentionally
excluded from this repository.
