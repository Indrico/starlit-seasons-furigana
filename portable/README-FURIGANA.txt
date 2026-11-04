STARLIT SEASON FURIGANA - v0.2.0-alpha.1 PRERELEASE

Requires THE IDOLM@STER STARLIT SEASON 1.61 / Steam build 8278842 on Windows x64.
The UE4SS loader, prebuilt native bridge, and furigana annotations are included.
No Python, compilation, extraction tools, or separate downloads are needed.

FRESH INSTALLATION
1. Close the game.
2. Open Steam > game Properties > Installed Files > Browse.
3. Extract ALL contents of this ZIP into that folder, next to StarlitSeason.exe.
   Merge the included StarlitSeason folder with the existing one.
4. Double-click Check-Furigana.cmd once. Wait for the successful check.
5. Launch the game normally through Steam and use Japanese dialogue.
6. The mod starts enabled with manual dialogue. Use the normal advance input.

CONTROLS
Open OPTION and click "Furigana Mod: ON/OFF", or press F8 in that menu, to switch
ALL mod features on/off. The master preference is remembered across launches.
F6 switches manual/automatic dialogue and remembers that preference.
F7 switches furigana only. Manual/auto control stays independent of F7.

Complete dialogue and furigana appear together, at a fixed font size. The box
stays close to its original width. Long text uses pages; the normal advance
input turns a page before advancing the game. Auto mode waits at least three
seconds per page (or longer for more text). Startup logos are skipped while the
master switch is on. Turning it off restores native behavior; startup changes
apply on the next launch.

Automatic readings may contain errors.
Menus, character profiles, and lyrics are outside this version's scope.

PREFERENCES
StarlitFurigana/user-settings.ini stores enabled, manual, auto_min_seconds,
and auto_characters_per_second. The default timing is 3 seconds and 8 characters
per second. Close the game before editing timing values (valid range: 1-60).
This file is separate from protected runtime files and survives removal.

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
README can be removed. Preserve user-settings.ini if you want to retain your
preferences. A ue4ss folder containing logs may also remain.

The CMD files run the included PowerShell helper with a process-only execution
policy setting. They do not change the computer's persistent execution policy.

KNOWN TEST LIMITS
Functional checks include ordinary dialogue in Story and Album at 1920x1080,
manual/auto control, keyboard/mouse advance, and synthetic pagination. Every
cinema/novel/DLC layout, controller input, and a full playthrough remain open.
This version removes recurring global widget scans and reduces text preparation
work. Performance depends on hardware and scene; no fixed frame rate is promised.
See docs/performance.md in the repository for measurements and test limits.

PROJECT AND SUPPORT
https://github.com/Indrico/starlit-seasons-furigana
English development guide: docs/dialogue-controls.md in the repository.
UE4SS license and copyright notice: StarlitSeason/Binaries/Win64/ue4ss/LICENSE
MinHook license:
StarlitSeason/Binaries/Win64/ue4ss/Mods/StarlitFurigana/Scripts/MinHook.LICENSE.txt
