"""Installer tests use synthetic files only and never touch an installed game."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import install_mod as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.game = self.base / "game"
        self.bin = self.game / installer.BIN_REL
        self.bin.mkdir(parents=True)
        (self.game / "StarlitSeason.exe").write_bytes(b"synthetic launcher")
        (self.bin / "StarlitSeason-Win64-Shipping.exe").write_bytes(b"synthetic shipping exe")
        self.paks = self.game / "StarlitSeason/Content/Paks"
        self.paks.mkdir(parents=True)
        (self.paks / "original.pak").write_bytes(b"synthetic original pak")
        self.source = self.base / "project"
        (self.source / "config/UE4SS_Signatures").mkdir(parents=True)
        (self.source / "config/UE4SS-settings.ini").write_text("[General]\n", encoding="utf-8")
        (self.source / "config/UE4SS_Signatures/Game.lua").write_text("return {}", encoding="utf-8")
        (self.source / "mod/Scripts").mkdir(parents=True)
        for name in installer.SCRIPT_NAMES:
            (self.source / "mod/Scripts" / name).write_text("return {}", encoding="utf-8")
        self.readings = self.base / "readings.lua"
        self.readings.write_text("return {}", encoding="utf-8")
        self.loader = self.base / "loader.zip"
        self.write_loader()
        for name, value in (("PROJECT_ROOT", self.source), ("EXPECTED_LOADER_SHA256", installer.sha256(self.loader.read_bytes())),
                            ("EXPECTED_SHIPPING_SHA256", installer.sha256(b"synthetic shipping exe"))):
            patcher = patch.object(installer, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_loader(self, extra=None):
        with zipfile.ZipFile(self.loader, "w") as archive:
            archive.writestr("dwmapi.dll", b"synthetic proxy")
            archive.writestr("ue4ss/UE4SS.dll", b"synthetic loader")
            archive.writestr("ue4ss/Mods/UnwantedMod/Scripts/main.lua", "do_not_load()")
            if extra:
                info = zipfile.ZipInfo(extra)
                info.filename = extra  # Preserve a malicious raw backslash on Windows.
                archive.writestr(info, b"unsafe")

    def add_patch(self):
        folder = self.game / installer.PATCH_REL
        folder.mkdir()
        for name in installer.PATCH_NAMES:
            (folder / name).write_bytes(("original " + name).encode())

    def install(self):
        return installer.install(self.game, self.loader, self.readings)

    def test_clean_install_and_uninstall_preserve_game_and_extra_files(self):
        originals = {path: path.read_bytes() for path in (self.game / "StarlitSeason.exe", self.bin / "StarlitSeason-Win64-Shipping.exe", self.paks / "original.pak")}
        manifest = self.install()
        self.assertTrue((self.bin / "dwmapi.dll").is_file())
        self.assertFalse((self.bin / "ue4ss/Mods/UnwantedMod").exists())
        self.assertEqual((self.bin / "ue4ss/Mods/mods.txt").read_text(), "StarlitFurigana : 1\n")
        self.assertEqual(len(manifest["installed"]), len(installer.SCRIPT_NAMES) + 6)
        extra = self.bin / "ue4ss/user-created.log"
        extra.write_bytes(b"keep this")
        result = installer.uninstall(self.game)
        self.assertEqual(result["removed_files"], len(installer.SCRIPT_NAMES) + 6)
        self.assertEqual(extra.read_bytes(), b"keep this")
        self.assertFalse((self.bin / "dwmapi.dll").exists())
        self.assertFalse((self.game / installer.STATE_NAME).exists())
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_english_patch_pair_is_backed_up_and_restored_exactly(self):
        self.add_patch()
        source = self.game / installer.PATCH_REL
        original = {name: (source / name).read_bytes() for name in installer.PATCH_NAMES}
        manifest = self.install()
        self.assertEqual(len(manifest["backups"]), 2)
        for name in installer.PATCH_NAMES:
            self.assertFalse((source / name).exists())
            self.assertEqual((self.game / installer.STATE_NAME / "backups" / name).read_bytes(), original[name])
        installer.uninstall(self.game)
        for name in installer.PATCH_NAMES:
            self.assertEqual((source / name).read_bytes(), original[name])
        self.assertFalse((self.bin / "ue4ss").exists())

    def test_existing_loaders_or_state_are_refused(self):
        for path in (self.bin / "dwmapi.dll", self.bin / "ue4ss", self.game / installer.STATE_NAME):
            with self.subTest(path=path.name):
                if path.suffix:
                    path.write_bytes(b"existing")
                else:
                    path.mkdir()
                with self.assertRaisesRegex(installer.InstallError, "Existing loader"):
                    self.install()
                if path.is_file():
                    self.assertEqual(path.read_bytes(), b"existing")
                    path.unlink()
                else:
                    path.rmdir()

    def test_changed_owned_file_blocks_uninstall_before_any_mutation(self):
        self.add_patch()
        manifest = self.install()
        changed = self.game / installer.MOD_REL / "main.lua"
        changed.write_bytes(b"user edit")
        with self.assertRaisesRegex(installer.InstallError, "was changed"):
            installer.uninstall(self.game)
        self.assertEqual(changed.read_bytes(), b"user edit")
        self.assertTrue((self.bin / "dwmapi.dll").exists())
        self.assertEqual(len(manifest["backups"]), 2)
        self.assertFalse((self.game / installer.PATCH_REL / installer.PATCH_NAMES[0]).exists())

    def test_malicious_zip_members_are_refused(self):
        for name in ("../escape.dll", "/absolute.dll", "C:/drive.dll", "bad\\member.dll", "DWMAPI.DLL"):
            with self.subTest(member=name):
                self.write_loader(name)
                with patch.object(installer, "EXPECTED_LOADER_SHA256", installer.sha256(self.loader.read_bytes())):
                    with self.assertRaisesRegex(installer.InstallError, "ZIP member"):
                        self.install()
                self.assertFalse((self.game / installer.STATE_NAME).exists())
                self.assertFalse((self.bin / "dwmapi.dll").exists())
                self.assertFalse((self.base / "escape.dll").exists())

    def test_unrecognized_loader_and_game_build_are_refused(self):
        with patch.object(installer, "EXPECTED_LOADER_SHA256", "0" * 64):
            with self.assertRaisesRegex(installer.InstallError, "Loader ZIP SHA-256"):
                self.install()
        (self.bin / "StarlitSeason-Win64-Shipping.exe").write_bytes(b"different game build")
        with self.assertRaisesRegex(installer.InstallError, "supported game build"):
            self.install()
        self.assertFalse((self.game / installer.STATE_NAME).exists())

    def test_occupied_patch_restore_path_blocks_uninstall(self):
        self.add_patch()
        self.install()
        path = self.game / installer.PATCH_REL / installer.PATCH_NAMES[0]
        path.write_bytes(b"new user patch")
        with self.assertRaisesRegex(installer.InstallError, "destination is occupied"):
            installer.uninstall(self.game)
        self.assertEqual(path.read_bytes(), b"new user patch")
        self.assertTrue((self.bin / "dwmapi.dll").exists())

    def test_copy_failure_rolls_back_installed_files_and_patch_moves(self):
        self.add_patch()
        original_open = Path.open

        def fail_one_copy(path, mode="r", *args, **kwargs):
            if mode == "xb" and path.name == "UE4SS-settings.ini":
                raise OSError("synthetic file-lock failure")
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", fail_one_copy):
            with self.assertRaisesRegex(installer.InstallError, "rolled back"):
                self.install()
        self.assertFalse((self.bin / "dwmapi.dll").exists())
        self.assertFalse((self.bin / "ue4ss").exists())
        self.assertFalse((self.game / installer.STATE_NAME).exists())
        for name in installer.PATCH_NAMES:
            self.assertEqual((self.game / installer.PATCH_REL / name).read_bytes(), ("original " + name).encode())

    def test_tampered_manifest_cannot_remove_game_executable(self):
        self.install()
        path = self.game / installer.STATE_NAME / "manifest.json"
        manifest = json.loads(path.read_text())
        original = self.game / "StarlitSeason.exe"
        manifest["installed"].append({"path": "StarlitSeason.exe", "sha256": hashlib.sha256(original.read_bytes()).hexdigest()})
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(installer.InstallError, "unowned path"):
            installer.uninstall(self.game)
        self.assertEqual(original.read_bytes(), b"synthetic launcher")
        self.assertTrue((self.bin / "dwmapi.dll").exists())

    def test_missing_input_does_not_move_english_patch(self):
        self.add_patch()
        self.readings.unlink()
        with self.assertRaises(FileNotFoundError):
            self.install()
        self.assertFalse((self.game / installer.STATE_NAME).exists())
        for name in installer.PATCH_NAMES:
            self.assertTrue((self.game / installer.PATCH_REL / name).is_file())

    def test_native_bridge_is_owned_but_preferences_survive_removal(self):
        native = self.base / 'native.dll'
        native.write_bytes(b'synthetic native bridge')
        license_file = self.source / 'native/vendor/minhook/LICENSE.txt'
        license_file.parent.mkdir(parents=True)
        license_file.write_bytes(b'synthetic license')
        manifest = installer.install(self.game, self.loader, self.readings, native)
        installed = self.game / installer.MOD_REL / 'StarlitFuriganaNative.dll'
        self.assertEqual(installed.read_bytes(), native.read_bytes())
        settings = self.game / 'StarlitFurigana/user-settings.ini'
        settings.write_text('manual = false\n', encoding='utf-8')
        self.assertFalse(any(item['path'].endswith('user-settings.ini') for item in manifest['installed']))
        installer.uninstall(self.game)
        self.assertFalse(installed.exists())
        self.assertEqual(settings.read_text(), 'manual = false\n')

    def test_uninstall_file_lock_rolls_back_before_restoring_patch(self):
        self.add_patch()
        manifest = self.install()
        original_rename = Path.rename

        def fail_locked_loader(path, destination):
            if path == self.bin / "ue4ss/UE4SS.dll":
                raise OSError("synthetic loaded-DLL lock")
            return original_rename(path, destination)

        with patch.object(Path, "rename", fail_locked_loader):
            with self.assertRaisesRegex(installer.InstallError, "installation was restored"):
                installer.uninstall(self.game)
        for item in manifest["installed"]:
            self.assertEqual(installer.sha256((self.game / item["path"]).read_bytes()), item["sha256"])
        for name in installer.PATCH_NAMES:
            self.assertFalse((self.game / installer.PATCH_REL / name).exists())
            self.assertTrue((self.game / installer.STATE_NAME / "backups" / name).exists())


if __name__ == "__main__":
    unittest.main()
