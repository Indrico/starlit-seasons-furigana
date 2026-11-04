# Drag-and-drop installation — v0.1.0-alpha.2

The Windows package includes the UE4SS loader and prebuilt furigana annotations.
**No Python, compilation, game-data extraction, or separate downloads are needed.**

This page describes the published **v0.1.0-alpha.2** package. The current `main`
branch also has v0.2 dialogue controls, a compact native-width window, an Options
master switch, and logo skipping; those changes are being verified separately.
See [development controls](dialogue-controls.md) for that version. The published
alpha.2 asset remains unchanged.

## Fresh installation

1. Download **`starlit-season-furigana-v0.1.0-alpha.2-windows-x64.zip`** from the
   [release page](https://github.com/Indrico/starlit-seasons-furigana/releases/tag/v0.1.0-alpha.2).
   Choose this asset rather than GitHub's automatic **Source code** archives.
2. Close the game. In Steam, open **Properties → Installed Files → Browse**.
3. Extract **all contents** of the ZIP into that game folder, next to
   **`StarlitSeason.exe`**. Merge the included `StarlitSeason` folder with the
   existing folder. Do not put the ZIP or its contents in `Paks/~mods`.
4. Double-click **`Check-Furigana.cmd`** once and wait for the successful check.
5. Launch the game normally through **Steam**, using Japanese dialogue.

The final folder layout includes:

```text
StarlitSeason.exe                  (existing game launcher)
Check-Furigana.cmd
Uninstall-Furigana.cmd
README-FURIGANA.txt
StarlitFurigana/
    manage.ps1
    manifest.json
StarlitSeason/
    Binaries/Win64/
        StarlitSeason-Win64-Shipping.exe  (existing game executable)
        dwmapi.dll
        ue4ss/
```

The checker validates the exact game build and all package runtime hashes.
If the known `pakchunk99-EngPatch.pak` and `.sig` are present, it backs them up
outside the PAK loading directory and disables them. Other translation mods are
not handled automatically. Original executables, base PAKs, and saves are not
rewritten.

## In the game

Furigana starts enabled. Open a Japanese conversation or answer-choice scene.
Readings appear above annotated kanji after a complete matching line finishes
revealing and remains stable for 250 ms. Press **F7** to turn furigana off or on.

## Requirements and existing installations

- Windows x64, game **1.61 / Steam build `8278842`**.
- A fresh game runtime without an existing UE4SS loader.
- For another game build, stop if the checker reports a mismatch; these native
  signatures have only been verified against the supported executable.

If an older furigana version or another loader is installed, uninstall or
preserve it **before copying this ZIP**. Do not overwrite another loader or an
older managed installation. Python-managed versions use the uninstall command
in [installation and removal](installation.md). Portable versions use
`Uninstall-Furigana.cmd`; preserve any leftover `ue4ss` logs elsewhere before
installing again.

## Remove the mod

Close the game and double-click **`Uninstall-Furigana.cmd`**. It checks owned-file
hashes, removes the matching runtime files, and restores English-patch files that
the checker backed up. Modified package files block removal until you preserve
your edits and restore their expected contents.

Keep `.starlit-furigana-portable-state` under the game root until removal
completes; it holds patch backups. Logs and unrelated files remain. After removal,
you can remove the `StarlitFurigana` helper folder, both Furigana CMD files, and
`README-FURIGANA.txt`.

## Package contents and limits

Prebuilt annotations cover **49,749 distinct source strings with readings**.
They store source hashes, byte positions, and kana only. The base text comes
from the running game; the package excludes original dialogue, game archives,
fonts, saves, and resource keys. UE4SS is bundled with its original MIT license
at `StarlitSeason/Binaries/Win64/ue4ss/LICENSE`.

Readings are automatic and may be wrong. Menus, profiles, and lyrics are outside
this version's scope; unsupported text/layouts keep native rendering. Normal-play
choice input, controller input, true 1080p rendering, and a full playthrough
remain unverified. See [runtime verification](runtime.md).

`SHA256SUMS.txt` on the release page contains the download checksum. Developers
can use the optional [source-build workflow](build-from-source.md).
