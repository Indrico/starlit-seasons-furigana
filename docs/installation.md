# Install and remove the local mod

This alpha has been tested locally on the supported build. See [runtime verification](runtime.md) for observed behavior and limits. Source unit tests alone do not establish compatibility with another build.

Close Starlit Season completely before installing or uninstalling. The installer does not terminate game processes. Windows file-lock errors cause the operation to fail and trigger rollback rather than replacing a locked loader.

## Requirements

- The supported local game build, identified by Shipping EXE SHA-256 `881df05d33a9b25d276122f010169d790e6cee18667136983f8bef0caa6bf2c2`. Unknown builds are refused at installation because the signatures are specific to this executable.
- The pinned [UE4SS 3.0.1-1196-g236adf26 ZIP](https://github.com/UE4SS-RE/RE-UE4SS/releases/download/experimental-latest/UE4SS_v3.0.1-1196-g236adf26.zip), SHA-256 `75dc8b081d324fe0598a87b26e37d13a84d3648cbb1d08eb48c514376407a11b`. The installer reads an existing local download and does not download a loader.
- Generated local `readings.lua`, built from your own original Japanese game text using the documented reading pipeline.
- This repository's `mod/Scripts` and `config` source files.

The installer refuses to proceed if `dwmapi.dll`, an `ue4ss` directory, or `.starlit-furigana-state` already exists in its target location. First uninstall an earlier managed installation, or move another loader aside yourself. Existing third-party loader installations are never merged automatically.

## Install

From the repository root, with `--game` pointing to the installation root containing `StarlitSeason.exe`:

```powershell
python tools/install_mod.py --game 'D:\SteamLibrary\steamapps\common\StarlitSeason' --loader-zip '.local\ue4ss-experimental.zip' --readings '.local\generated\readings.lua'
```

All inputs are read, staged, and checked before the runtime tree changes. The installer copies only `dwmapi.dll` and `ue4ss/UE4SS.dll` from the ZIP; bundled sample mods and default configurations are excluded. It adds the project settings, signatures, furigana scripts, reading table, and a `mods.txt` enabling only `StarlitFurigana`.

If present, `pakchunk99-EngPatch.pak` and its `.sig` are moved out of `Content/Paks/~mods` together into `.starlit-furigana-state/backups` under the game root. That directory is outside the PAK loading tree. Each present patch file is recorded separately, so a partial pre-existing pair is preserved without inventing a missing counterpart.

The ownership manifest records the relative path and SHA-256 of every installed file, plus the exact source and backup paths of the English patch. Original executables, base PAK archives, other mods, and saves are not rewritten. A failed installation restores moved patches and removes the files created by that attempt. If rollback itself fails, recovery information and backups remain in the state directory.

## Uninstall

Close the game, then run:

```powershell
python tools/install_mod.py --game 'D:\SteamLibrary\steamapps\common\StarlitSeason' --uninstall
```

Uninstallation first checks every existing managed file against its recorded hash. It refuses to continue if a file was edited, a patch backup changed, or a patch restore destination is occupied. Preserve your edits elsewhere before retrying. No files are removed before these checks pass.

Only matching managed files are removed, and the original English patch files are restored to their recorded locations. Only empty directories are removed. Runtime-created logs and unrelated user files remain; consequently an `ue4ss` directory containing those files can survive uninstallation and must be moved aside before another installation.

If a file-lock error interrupts removal, the installer attempts to restore the installation. Recovery data is retained if rollback cannot finish. Uninstallation does not require the game executable to retain its original build hash, allowing the mod to be removed after a game update.

## Synthetic installer tests

These tests use temporary mock game files and never operate on an installed game:

```powershell
python -m unittest discover -s tools -p test_install_mod.py -v
```

They cover clean installation/removal, exact English-patch restoration, existing-loader refusal, edited-file refusal, malicious ZIP paths, unsupported checksums, occupied restore paths, rollback after a simulated copy failure, and a tampered manifest attempting to name a game executable.

## Local installation check

On 2026-11-03, the real supported installation completed an install/uninstall
round trip: 11 managed files were removed and both English-patch files were
restored with identical SHA-256 hashes. The mod was then installed again and
launched normally through Steam with only the managed runtime files. The
Shipping executable retained its original supported hash.

Removal was also repeated after actual game use: ownership checks passed, both
patch files were restored again, and runtime-created logs survived removal as
intended. The final local setup was reinstalled with furigana enabled.
