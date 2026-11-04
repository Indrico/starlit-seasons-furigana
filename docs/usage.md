# Drag-and-drop installation — v0.2.0-alpha.1

The Windows package includes the UE4SS loader, compiled native bridge, and prebuilt furigana annotations.
**No Python, compilation, game-data extraction, or separate downloads are needed.**

This version adds manual dialogue, complete text and furigana together, fixed
fonts in a compact window, an Options master switch, startup-logo skipping, and
reduced recurring discovery overhead. See [controls](dialogue-controls.md) and
[performance measurements](performance.md). The historical alpha.2 asset is unchanged.

## Fresh installation

1. Download **`starlit-season-furigana-v0.2.0-alpha.1-windows-x64.zip`** from the
   [release page](https://github.com/Indrico/starlit-seasons-furigana/releases/tag/v0.2.0-alpha.1).
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

The mod starts enabled, with manual dialogue. Complete dialogue and furigana
are prepared together at fixed font sizes. Use the normal advance input to
continue; long dialogue turns pages before advancing the game. Voice playback
and character animation continue while a manual line is held.

| Control | Action |
| --- | --- |
| Normal advance input | Turn a page, or continue after the final page |
| F6 | Switch manual/automatic dialogue; the preference is saved |
| F7 | Toggle furigana independently of manual/automatic progression |
| OPTION → Furigana Mod: ON/OFF | Toggle all mod features; the preference is saved |
| F8 while OPTION is open | Keyboard equivalent of the master switch |

Startup logos are skipped while the master switch is on. Switching it off
restores native behavior; the startup preference applies on the next launch.
Automatic mode waits at least three seconds per page, and longer for more text.
Preferences are stored in `StarlitFurigana/user-settings.ini`. Close the game
before editing timing values; see [preferences](dialogue-controls.md).

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
`README-FURIGANA.txt`. Preserve `StarlitFurigana/user-settings.ini` to keep your
preferences when upgrading or reinstalling.

## Package contents and limits

Prebuilt annotations cover **49,749 distinct source strings with readings**.
They store source hashes, byte positions, and kana only. The base text comes
from the running game; the package excludes original dialogue, game archives,
fonts, saves, and resource keys. UE4SS is bundled with its original MIT license
at `StarlitSeason/Binaries/Win64/ue4ss/LICENSE`. The compiled native bridge
includes MinHook's license in its Scripts directory.

Readings are automatic and may be wrong. Menus, profiles, and lyrics are outside
this version's scope; unsupported text/layouts keep native rendering. Normal-play
choice input, controller input, every cinema/novel/DLC layout, and a full playthrough
remain unverified. See [runtime verification](runtime.md).

`SHA256SUMS.txt` on the release page contains the download checksum. Developers
can use the optional [source-build workflow](build-from-source.md).
