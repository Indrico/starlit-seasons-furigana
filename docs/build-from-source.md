# Build from source

Most players should use the [drag-and-drop package](usage.md). This optional
workflow builds a private reading table and uses the Python installer.

## If the mod is already installed

1. Launch **THE IDOLM@STER STARLIT SEASON** normally through Steam.
2. Open a Japanese conversation or an answer-choice scene.
3. Furigana starts enabled. Small kana appear above annotated kanji after a
   complete matching line finishes revealing and remains stable for 250 ms.
4. Press **F7** to turn furigana off or on. Turning it off restores native text.

The local installation used to develop this release is already configured.
Downloading the release does not require reinstalling that setup.

## What to download

On the [release page](https://github.com/Indrico/starlit-seasons-furigana/releases/tag/v0.1.0-alpha.2),
download GitHub's **Source code (zip)** archive. Extract it to a
working folder outside the game's installation, then open PowerShell in the
extracted folder containing `README.md`.

This source archive includes the Lua mod, installer,
reading generator, extraction tools, tests, and English documentation. It does
not include game assets, the original dialogue corpus, generated readings,
resource keys, or the UE4SS loader. The steps below prepare those inputs locally.
Do not copy the source ZIP directly into the game's `Paks` directory.

`SHA256SUMS.txt` on the release page applies to the ready-to-use Windows package.

## First installation

### 1. Check requirements

- Windows x64 and your installed Steam copy of the game.
- Game 1.61 / Steam build `8278842`. The installer checks the Shipping EXE's exact
  SHA-256 and refuses unsupported builds. See [installation details](installation.md).
- 64-bit Python 3.10, the Python version tested for this release.
- Internet access to install Python dependencies and download the pinned loader.
- A folder for private extracted assets and generated readings.

The installer does not merge another UE4SS installation. If you have an existing
managed installation, use its uninstall command before installing again. Preserve
any third-party loader separately before attempting a first installation.

### 2. Set up the tools and download UE4SS

Run these commands from the extracted release folder. Change `$gameRoot` to the
folder containing your `StarlitSeason.exe`:

```powershell
$gameRoot = 'D:\SteamLibrary\steamapps\common\StarlitSeason'
$privateRoot = Join-Path $PWD '.local'
New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt

Invoke-WebRequest -Uri 'https://github.com/UE4SS-RE/RE-UE4SS/releases/download/experimental-latest/UE4SS_v3.0.1-1196-g236adf26.zip' -OutFile "$privateRoot/ue4ss.zip"
```

Use that exact UE4SS archive. Its expected SHA-256 is
`75dc8b081d324fe0598a87b26e37d13a84d3648cbb1d08eb48c514376407a11b`;
the installer verifies it. Do not substitute another experimental build.

### 3. Prepare private Japanese text

Start the game normally through Steam and wait for the title screen. In the same
PowerShell session, list the running game process:

```powershell
Get-Process -Name 'StarlitSeason-Win64-Shipping' | Select-Object Id, Path
```

Set `$gamePid` below to the displayed ID whose path belongs to `$gameRoot`.
`12345` is only a placeholder:

```powershell
$gamePid = 12345
& '.\.venv\Scripts\python.exe' tools/extraction/recover_local_pak_key.py --pid $gamePid --game "$gameRoot" --pak "$gameRoot/StarlitSeason/Content/Paks/pakchunk0-WindowsNoEditor.pak" --output "$privateRoot/evidence"
```

The recovery tool uses read-only process access and validates the resource key
against the archive index. It does not patch the executable. If the command
fails, stop here and read its error; do not proceed with missing inputs.

**Close the game completely now.** Keep the same PowerShell session open, then
run each command below in order. Continue only when the preceding command
succeeds:

```powershell
& '.\.venv\Scripts\python.exe' tools/extraction/extract_original.py --game "$gameRoot" --key-file "$privateRoot/evidence/pak-key.hex" --output "$privateRoot/original"
& '.\.venv\Scripts\python.exe' tools/extraction/corpus_extract.py --input "$privateRoot/original/StarlitSeason/Content/Commu/Localize" --output "$privateRoot/corpus"
& '.\.venv\Scripts\python.exe' tools/extraction/localization_extract.py --content "$privateRoot/original/StarlitSeason/Content" --output "$privateRoot"
& '.\.venv\Scripts\python.exe' tools/readings/generate.py "$privateRoot/corpus/dialogue.jsonl" --profiles "$privateRoot/character-profiles-resolved.json" --output "$privateRoot/generated"
```

Keep `.local` private. It contains extracted game text, generated data, and the
resource key. It is excluded from Git and is not a release upload.

### 4. Install and play

With the game still closed:

```powershell
& '.\.venv\Scripts\python.exe' tools/install_mod.py --game "$gameRoot" --loader-zip "$privateRoot/ue4ss.zip" --readings "$privateRoot/generated/readings.lua"
```

The installer adds the mod runtime and records its ownership hashes. If the known
`pakchunk99-EngPatch.pak` and `.sig` files are present, it backs them up outside
the PAK loading directory and disables them. Original executables, base PAKs,
other mods, and saves are not rewritten.

Launch through Steam and use Japanese text. Start a conversation to see the
furigana. **F7** toggles annotations; no mod menu or Lua console is needed.

## Remove the mod

Close the game. From the extracted release folder, run the following with your
actual game path:

```powershell
& '.\.venv\Scripts\python.exe' tools/install_mod.py --game 'D:\SteamLibrary\steamapps\common\StarlitSeason' --uninstall
```

Removal checks owned-file hashes, removes matching mod files, and restores the
backed-up English patch. Keep `.starlit-furigana-state` under the game root until
removal is complete. Do not delete that backup directory manually.

Logs and unrelated files survive removal. An `ue4ss` folder containing logs can
remain afterward; preserve it elsewhere before reinstalling. If removal reports
an edited managed file, preserve your edits and see [installation and removal](installation.md).

## Limits and troubleshooting

- **No furigana during text reveal:** this is expected. Readings appear after a
  complete exact-source match remains stable for 250 ms.
- **Some text remains unchanged:** menus, profiles, and lyrics are outside this
  version's scope. Unsupported markup, unmatched substituted text, and layouts
  that do not fit keep the native renderer.
- **An incorrect reading:** readings are automatic and have not all been reviewed.
  See the [reading pipeline](reading-pipeline.md) for local corrections.
- **An unsupported-build or loader error:** use the exact supported game and
  pinned loader; the installer intentionally refuses other hashes.
- **An existing-loader error:** the installer does not overwrite another loader
  or an existing managed installation.

Dialogue, fitted two-line text, three answer labels, and F7 were observed at
1680 by 1050. Interactive choice input in normal play, controller input, true
1080p rendering, and a complete playthrough remain unverified. See
[runtime verification](runtime.md) for the recorded results.
