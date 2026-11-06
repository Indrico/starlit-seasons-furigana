"""Install/uninstall the local furigana mod without replacing game assets.

Close the game before either operation. Inputs are local files; nothing is
downloaded, and no game executable, original PAK, or save is rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LOADER_SHA256 = "75dc8b081d324fe0598a87b26e37d13a84d3648cbb1d08eb48c514376407a11b"
EXPECTED_SHIPPING_SHA256 = "881df05d33a9b25d276122f010169d790e6cee18667136983f8bef0caa6bf2c2"
STATE_NAME = ".starlit-furigana-state"
BIN_REL = "StarlitSeason/Binaries/Win64"
MOD_REL = f"{BIN_REL}/ue4ss/Mods/StarlitFurigana/Scripts"
PATCH_REL = "StarlitSeason/Content/Paks/~mods"
PATCH_NAMES = ("pakchunk99-EngPatch.pak", "pakchunk99-EngPatch.sig")
SCRIPT_NAMES = ("main.lua", "umg_ruby.lua", "ruby_layout.lua", "reading_lookup.lua", "sha256.lua",
                "native_bridge.lua", "dialogue_controller.lua", "settings.lua", "mod_menu.lua", "startup.lua",
                "object_registry.lua", "ui_annotations.lua", "ui_geometry.lua", "ui_bindings.lua", "backlog.lua",
                "performance_guard.lua")


class InstallError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inside(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if not relative or "\\" in relative or ":" in relative or pure.is_absolute() or ".." in pure.parts:
        raise InstallError(f"Unsafe relative path: {relative!r}")
    path = root.joinpath(*pure.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise InstallError(f"Path leaves selected game directory: {relative}")
    return path


def _game_root(game: Path) -> Path:
    root = game.resolve(strict=True)
    if not (root / "StarlitSeason.exe").is_file() or not (root / BIN_REL / "StarlitSeason-Win64-Shipping.exe").is_file():
        raise InstallError("--game must be the Starlit Season installation root")
    if not (root / "StarlitSeason/Content/Paks").is_dir():
        raise InstallError("The selected installation has no Content/Paks directory")
    return root


def _owned_path(relative: str) -> bool:
    exact = {
        f"{BIN_REL}/dwmapi.dll", f"{BIN_REL}/ue4ss/UE4SS.dll",
        f"{BIN_REL}/ue4ss/UE4SS-settings.ini", f"{BIN_REL}/ue4ss/Mods/mods.txt",
        *(f"{MOD_REL}/{name}" for name in (*SCRIPT_NAMES, "readings.lua")),
        f"{MOD_REL}/StarlitFuriganaNative.dll", f"{MOD_REL}/MinHook.LICENSE.txt",
    }
    signature_prefix = f"{BIN_REL}/ue4ss/UE4SS_Signatures/"
    return relative in exact or (
        relative.startswith(signature_prefix)
        and "/" not in relative[len(signature_prefix):]
        and relative.endswith(".lua")
    )


def _loader_members(loader_zip: Path) -> dict[str, bytes]:
    raw = loader_zip.read_bytes()
    if sha256(raw) != EXPECTED_LOADER_SHA256:
        raise InstallError("Loader ZIP SHA-256 does not match the pinned UE4SS archive")
    with zipfile.ZipFile(loader_zip) as archive:
        seen: set[str] = set()
        for member in archive.infolist():
            # ZipInfo normalizes Windows separators; inspect its original name.
            name = member.orig_filename
            pure = PurePosixPath(name)
            if (not name or "\x00" in name or "\\" in name or ":" in name or pure.is_absolute()
                    or ".." in pure.parts or stat.S_ISLNK(member.external_attr >> 16)):
                raise InstallError(f"Unsafe ZIP member: {name!r}")
            canonical = str(pure).casefold()
            if canonical in seen:
                raise InstallError(f"Duplicate ZIP member: {name!r}")
            seen.add(canonical)
        required = ("dwmapi.dll", "ue4ss/UE4SS.dll")
        if any(name not in archive.namelist() for name in required):
            raise InstallError("Loader ZIP is missing a required DLL")
        return {f"{BIN_REL}/{name}": archive.read(name) for name in required}


def _inputs(loader_zip: Path, readings: Path, native_dll: Path | None = None, ui_bindings: Path | None = None) -> dict[str, bytes]:
    files = _loader_members(loader_zip)
    files[f"{BIN_REL}/ue4ss/UE4SS-settings.ini"] = (PROJECT_ROOT / "config/UE4SS-settings.ini").read_bytes()
    signatures = sorted((PROJECT_ROOT / "config/UE4SS_Signatures").glob("*.lua"))
    if not signatures:
        raise InstallError("Project has no game signature configuration")
    for source in signatures:
        files[f"{BIN_REL}/ue4ss/UE4SS_Signatures/{source.name}"] = source.read_bytes()
    for name in SCRIPT_NAMES:
        files[f"{MOD_REL}/{name}"] = (PROJECT_ROOT / "mod/Scripts" / name).read_bytes()
    files[f"{MOD_REL}/readings.lua"] = readings.read_bytes()
    if ui_bindings is not None:
        files[f"{MOD_REL}/ui_bindings.lua"] = ui_bindings.read_bytes()
    files[f"{BIN_REL}/ue4ss/Mods/mods.txt"] = b"StarlitFurigana : 1\n"
    if not files[f"{MOD_REL}/readings.lua"]:
        raise InstallError("Generated readings file is empty")
    if native_dll is not None:
        files[f"{MOD_REL}/StarlitFuriganaNative.dll"] = native_dll.read_bytes()
        files[f"{MOD_REL}/MinHook.LICENSE.txt"] = (PROJECT_ROOT / "native/vendor/minhook/LICENSE.txt").read_bytes()
    return files


def _mkdirs(root: Path, path: Path, created: list[str]):
    missing = []
    cursor = path
    while cursor != root and not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory.relative_to(root).as_posix())


def _remove_empty(root: Path, directories: list[str]):
    for relative in sorted(set(directories), key=lambda name: name.count("/"), reverse=True):
        path = _inside(root, relative)
        try:
            path.rmdir()
        except (FileNotFoundError, OSError):
            # Runtime-created logs or user files must survive removal.
            pass


def install(game: Path, loader_zip: Path, readings: Path, native_dll: Path | None = None, ui_bindings: Path | None = None) -> dict:
    root = _game_root(game)
    state = _inside(root, STATE_NAME)
    if state.exists() or (root / BIN_REL / "dwmapi.dll").exists() or (root / BIN_REL / "ue4ss").exists():
        raise InstallError("Existing loader or installer state found; uninstall or move it aside first")
    shipping = root / BIN_REL / "StarlitSeason-Win64-Shipping.exe"
    if sha256(shipping.read_bytes()) != EXPECTED_SHIPPING_SHA256:
        raise InstallError("Shipping EXE does not match the supported game build; installation refused")
    files = _inputs(loader_zip, readings, native_dll, ui_bindings)
    backups = []
    for name in PATCH_NAMES:
        relative = f"{PATCH_REL}/{name}"
        source = _inside(root, relative)
        if source.exists():
            if source.is_symlink() or not source.is_file():
                raise InstallError(f"English patch is not a regular file: {relative}")
            backups.append({"source": relative, "stored": f"backups/{name}", "sha256": sha256(source.read_bytes())})
    installed = [{"path": relative, "sha256": sha256(data)} for relative, data in sorted(files.items())]
    manifest = {"version": 1, "loader_zip_sha256": EXPECTED_LOADER_SHA256, "installed": installed, "backups": backups, "directories": []}
    created_files: list[str] = []
    moved_backups: list[dict] = []
    created_dirs: list[str] = []
    # All inputs are staged and verified before touching the loaded game tree.
    with tempfile.TemporaryDirectory(prefix="starlit-furigana-stage-") as temporary:
        stage = Path(temporary)
        for relative, data in files.items():
            target = _inside(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if sha256(target.read_bytes()) != sha256(data):
                raise InstallError(f"Failed to stage {relative}")
        state.mkdir()
        try:
            if native_dll is not None:
                _mkdirs(root, _inside(root, "StarlitFurigana"), created_dirs)
            for backup in backups:
                stored = _inside(state, backup["stored"])
                stored.parent.mkdir(exist_ok=True)
                _inside(root, backup["source"]).rename(stored)
                moved_backups.append(backup)
            for relative in sorted(files):
                destination = _inside(root, relative)
                _mkdirs(root, destination.parent, created_dirs)
                with destination.open("xb") as output:
                    created_files.append(relative)
                    output.write(_inside(stage, relative).read_bytes())
                if sha256(destination.read_bytes()) != sha256(files[relative]):
                    raise InstallError(f"Installed-file verification failed: {relative}")
            manifest["directories"] = created_dirs
            (state / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception as error:
            rollback_errors = []
            for relative in reversed(created_files):
                try:
                    _inside(root, relative).unlink()
                except OSError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            for backup in reversed(moved_backups):
                try:
                    source = _inside(root, backup["source"])
                    if source.exists():
                        raise InstallError(f"Cannot restore occupied patch path: {backup['source']}")
                    _inside(state, backup["stored"]).rename(source)
                except (OSError, InstallError) as rollback_error:
                    rollback_errors.append(str(rollback_error))
            _remove_empty(root, created_dirs)
            if rollback_errors:
                (state / "recovery.json").write_text(json.dumps({"manifest": manifest, "errors": rollback_errors}, indent=2), encoding="utf-8")
                raise InstallError(f"Install failed; recovery files retained in {state}") from error
            for path in (state / "manifest.json",):
                if path.exists():
                    path.unlink()
            _remove_empty(state, ["backups"])
            state.rmdir()
            raise InstallError(f"Install failed and was rolled back: {error}") from error
    return manifest


def uninstall(game: Path) -> dict:
    root = _game_root(game)
    state = _inside(root, STATE_NAME)
    manifest_path = state / "manifest.json"
    if not manifest_path.is_file():
        raise InstallError("No completed installer manifest found for this game")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise InstallError("Unsupported installer manifest version")
    installed = manifest.get("installed", [])
    backups = manifest.get("backups", [])
    if not installed or len({item["path"] for item in installed}) != len(installed):
        raise InstallError("Invalid installed-file manifest")
    # Validate every operation before removing or restoring anything.
    for item in installed:
        relative = item["path"]
        if not _owned_path(relative) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise InstallError(f"Manifest contains an unowned path: {relative}")
        path = _inside(root, relative)
        if path.exists() and (path.is_symlink() or not path.is_file() or sha256(path.read_bytes()) != item["sha256"]):
            raise InstallError(f"Installed file was changed; preserve your edits before uninstalling: {relative}")
    for backup in backups:
        name = PurePosixPath(backup["source"]).name
        if name not in PATCH_NAMES or backup["source"] != f"{PATCH_REL}/{name}" or backup["stored"] != f"backups/{name}":
            raise InstallError("Invalid patch backup path in manifest")
        stored = _inside(state, backup["stored"])
        if not stored.is_file() or stored.is_symlink() or sha256(stored.read_bytes()) != backup["sha256"]:
            raise InstallError(f"Patch backup is missing or changed: {name}")
        if _inside(root, backup["source"]).exists():
            raise InstallError(f"Patch restore destination is occupied: {backup['source']}")
    for relative in manifest.get("directories", []):
        directory = _inside(root, relative)
        if relative != "StarlitFurigana" and (not relative.startswith(f"{BIN_REL}/ue4ss") or not directory.is_relative_to(root / BIN_REL / "ue4ss")):
            raise InstallError("Invalid installed directory in manifest")
    held: list[tuple[Path, Path]] = []
    restored: list[dict] = []
    hold_root = Path(tempfile.mkdtemp(prefix="uninstall-", dir=state))
    try:
        for item in installed:
            source = _inside(root, item["path"])
            if not source.exists():
                continue
            target = _inside(hold_root, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            held.append((source, target))
        for backup in backups:
            _inside(state, backup["stored"]).rename(_inside(root, backup["source"]))
            restored.append(backup)
    except Exception as error:
        rollback_errors = []
        for backup in reversed(restored):
            try:
                _inside(root, backup["source"]).rename(_inside(state, backup["stored"]))
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for source, target in reversed(held):
            try:
                target.rename(source)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            (state / "recovery.json").write_text(json.dumps({"errors": rollback_errors, "held_files": str(hold_root)}, indent=2), encoding="utf-8")
            raise InstallError(f"Uninstall failed; recovery files retained in {state}") from error
        _remove_empty(hold_root, [p.relative_to(hold_root).as_posix() for p in hold_root.rglob("*") if p.is_dir()])
        hold_root.rmdir()
        raise InstallError(f"Uninstall failed; installation was restored: {error}") from error
    # Only the files validated against the ownership hashes are deleted.
    for _, target in held:
        target.unlink()
    _remove_empty(hold_root, [p.relative_to(hold_root).as_posix() for p in hold_root.rglob("*") if p.is_dir()])
    hold_root.rmdir()
    manifest_path.unlink()
    _remove_empty(root, manifest.get("directories", []))
    _remove_empty(state, ["backups"])
    try:
        state.rmdir()
    except OSError:
        pass  # Preserve any unrelated files a user placed in installer state.
    return {"removed_files": len(held), "restored_patches": len(restored)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--loader-zip", type=Path)
    parser.add_argument("--readings", type=Path)
    parser.add_argument("--native-dll", type=Path, help="Precompiled bridge; omit only for the legacy renderer")
    parser.add_argument("--ui-bindings", type=Path, help="Generated hash-only UI/name bindings")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if not args.uninstall and (args.loader_zip is None or args.readings is None):
        parser.error("installation requires --loader-zip and --readings")
    try:
        result = uninstall(args.game) if args.uninstall else install(args.game, args.loader_zip, args.readings, args.native_dll, args.ui_bindings)
    except (InstallError, OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
