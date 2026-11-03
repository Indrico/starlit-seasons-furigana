STARLIT SEASON FURIGANA - DRAG-AND-DROP ALPHA

Requires THE IDOLM@STER STARLIT SEASON 1.61 / Steam build 8278842 on Windows x64.
The UE4SS loader and prebuilt furigana annotations are included.
No Python, compilation, extraction tools, or separate downloads are needed.

FRESH INSTALLATION
1. Close the game.
2. Open Steam > game Properties > Installed Files > Browse.
3. Extract ALL contents of this ZIP into that folder, next to StarlitSeason.exe.
   Merge the included StarlitSeason folder with the existing one.
4. Double-click Check-Furigana.cmd once. Wait for the successful check.
5. Launch the game normally through Steam and use Japanese dialogue.
6. Furigana starts enabled. Press F7 to turn it off or on.

Readings appear above annotated kanji after a complete matching line finishes
revealing and remains stable for 250 ms. Automatic readings may contain errors.
Menus, character profiles, and lyrics are outside this version's scope.

EXISTING MODS
This ZIP is intended for a fresh installation with no UE4SS loader installed.
Do not overwrite another loader or an older managed furigana installation.
Uninstall the old mod first. Check-Furigana.cmd will refuse older managed state.
The checker backs up pakchunk99-EngPatch.pak and its .sig, when present, outside
the PAK loading directory. Other translation mods are not handled automatically.

REMOVAL
Close the game and double-click Uninstall-Furigana.cmd.
The script verifies package hashes, removes owned runtime files, and restores
English-patch files that the checker backed up. Logs and unrelated files remain.
Keep .starlit-furigana-portable-state until removal completes; it holds backups.
After removal, the helper folder StarlitFurigana, the two CMD files, and this
README can be removed. A ue4ss folder containing logs may also remain.

The CMD files run the included PowerShell helper with a process-only execution
policy setting. They do not change the computer's persistent execution policy.

KNOWN TEST LIMITS
Visual checks cover ordinary dialogue, fitted two-line text, and three answer
labels at 1680x1050. Normal-play choice input, controllers, true 1080p, and a full
playthrough have not been certified.

PROJECT AND SUPPORT
https://github.com/Indrico/starlit-seasons-furigana
English guide: docs/usage.md in the repository.
UE4SS license and copyright notice: StarlitSeason/Binaries/Win64/ue4ss/LICENSE
