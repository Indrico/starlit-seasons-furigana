"""Exercise the shipped Windows helper on synthetic fresh game installations."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_release
import install_mod


@unittest.skipUnless(os.name == 'nt', 'The portable helper targets Windows PowerShell')
class PortableReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.game = self.base / 'Fresh game 日本語'
        self.game.mkdir()
        self.loader = self.base / 'loader.zip'
        with zipfile.ZipFile(self.loader, 'w') as archive:
            archive.writestr('dwmapi.dll', b'synthetic proxy')
            archive.writestr('ue4ss/UE4SS.dll', b'synthetic loader')
            archive.writestr('ue4ss/LICENSE', b'synthetic license')
            archive.writestr('ue4ss/Mods/Unwanted/Scripts/main.lua', b'do_not_include()')
        self.readings = self.base / 'readings.json'
        self.readings.write_text(json.dumps([{'source_text': '学校へ行く', 'segments': [
            {'base': '学校', 'reading': 'がっこう'}, {'base': 'へ'},
            {'base': '行', 'reading': 'い'}, {'base': 'く'}]}], ensure_ascii=False), encoding='utf-8')
        self.shipping = b'synthetic original Shipping executable'
        self.package = self.base / 'portable.zip'
        with patch.object(install_mod, 'EXPECTED_LOADER_SHA256', hashlib.sha256(self.loader.read_bytes()).hexdigest()), \
                patch.object(install_mod, 'EXPECTED_SHIPPING_SHA256', hashlib.sha256(self.shipping).hexdigest()):
            self.manifest = build_release.build(self.loader, self.readings, self.package)
        with zipfile.ZipFile(self.package) as archive:
            archive.extractall(self.game)
        (self.game / 'StarlitSeason.exe').write_bytes(b'synthetic original launcher')
        self.bin = self.game / install_mod.BIN_REL
        (self.bin / 'StarlitSeason-Win64-Shipping.exe').write_bytes(self.shipping)
        self.paks = self.game / 'StarlitSeason/Content/Paks'
        self.paks.mkdir(parents=True)
        (self.paks / 'original.pak').write_bytes(b'synthetic original game archive')

    def run_helper(self, action, success=True):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-File',
                                 str(self.game / 'StarlitFurigana/manage.ps1'), '-Action', action],
                                cwd=self.game, capture_output=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result.stdout

    def add_patch(self):
        folder = self.paks / '~mods'
        folder.mkdir()
        for name in install_mod.PATCH_NAMES:
            (folder / name).write_bytes(('original ' + name).encode())

    def assert_installed(self):
        for file in self.manifest['files']:
            self.assertEqual(hashlib.sha256((self.game / file['path']).read_bytes()).hexdigest(), file['sha256'])

    def test_package_is_self_contained_and_excludes_original_dialogue(self):
        with zipfile.ZipFile(self.package) as archive:
            names = archive.namelist()
            self.assertIn('Check-Furigana.cmd', names)
            self.assertIn('Uninstall-Furigana.cmd', names)
            self.assertIn(f'{install_mod.BIN_REL}/ue4ss/LICENSE', names)
            self.assertFalse(any(name.endswith(('.exe', '.pak', '.hex', '.jsonl')) for name in names))
            readings = archive.read(f'{install_mod.MOD_REL}/readings.lua').decode('utf-8')
            self.assertNotIn('学校', readings)
            self.assertIn('がっこう', readings)
            self.assertFalse(any('Unwanted' in name for name in names))

    def test_fresh_install_check_and_remove_preserve_game_and_unowned_files(self):
        self.run_helper('Prepare')
        self.assert_installed()
        log = self.bin / 'ue4ss/user.log'
        log.write_text('keep me')
        self.run_helper('Uninstall')
        self.assertEqual(log.read_text(), 'keep me')
        self.assertFalse((self.bin / 'dwmapi.dll').exists())
        self.assertEqual((self.bin / 'StarlitSeason-Win64-Shipping.exe').read_bytes(), self.shipping)
        self.assertEqual((self.paks / 'original.pak').read_bytes(), b'synthetic original game archive')

    def test_patch_backup_is_idempotent_and_restored_exactly(self):
        self.add_patch()
        self.run_helper('Prepare')
        self.run_helper('Prepare')
        for name in install_mod.PATCH_NAMES:
            self.assertFalse((self.paks / '~mods' / name).exists())
            self.assertEqual((self.game / '.starlit-furigana-portable-state/backups' / name).read_bytes(), ('original ' + name).encode())
        self.run_helper('Uninstall')
        for name in install_mod.PATCH_NAMES:
            self.assertEqual((self.paks / '~mods' / name).read_bytes(), ('original ' + name).encode())
        self.assertFalse((self.game / '.starlit-furigana-portable-state').exists())

    def test_wrong_game_build_does_not_move_patch(self):
        self.add_patch()
        (self.bin / 'StarlitSeason-Win64-Shipping.exe').write_bytes(b'unsupported build')
        output = self.run_helper('Prepare', False)
        self.assertIn('Unsupported game build', output)
        self.assertTrue((self.paks / '~mods' / install_mod.PATCH_NAMES[0]).exists())

    def test_changed_owned_file_blocks_removal_before_mutation(self):
        self.add_patch()
        self.run_helper('Prepare')
        changed = self.game / install_mod.MOD_REL / 'main.lua'
        changed.write_text('user edit')
        self.assertIn('was changed', self.run_helper('Uninstall', False))
        self.assertEqual(changed.read_text(), 'user edit')
        self.assertTrue((self.bin / 'dwmapi.dll').exists())
        self.assertFalse((self.paks / '~mods' / install_mod.PATCH_NAMES[0]).exists())

    def test_tampered_manifest_cannot_name_game_executable(self):
        path = self.game / 'StarlitFurigana/manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files'][0] = {'path': 'StarlitSeason.exe', 'sha256': hashlib.sha256((self.game / 'StarlitSeason.exe').read_bytes()).hexdigest()}
        path.write_text(json.dumps(manifest))
        self.assertIn('unowned', self.run_helper('Uninstall', False))
        self.assertTrue((self.game / 'StarlitSeason.exe').exists())
        self.assertTrue((self.bin / 'dwmapi.dll').exists())

    def test_locked_loader_rolls_back_removal_and_keeps_patch_backup(self):
        self.add_patch()
        self.run_helper('Prepare')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        # Permit hash reads but deny delete-sharing, so a rename fails mid-removal.
        handle = kernel.CreateFileW(str(self.bin / 'ue4ss/UE4SS.dll'), 0x80000000, 3, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.run_helper('Uninstall', False)
        finally:
            kernel.CloseHandle(handle)
        self.assert_installed()
        self.assertFalse((self.paks / '~mods' / install_mod.PATCH_NAMES[0]).exists())


if __name__ == '__main__':
    unittest.main()
