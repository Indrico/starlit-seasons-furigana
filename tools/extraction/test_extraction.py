"""Small format/validation fixtures; no game data or keys are embedded."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from Crypto.Cipher import AES

import asset_extract
from asset_extract import Pak
from corpus_extract import DataTable
from localization_extract import read_locres


def fstring(value, wide=False):
    if wide:
        encoded = value.encode('utf-16-le') + b'\0\0'
        return struct.pack('<i', -len(encoded) // 2) + encoded
    encoded = value.encode('utf-8') + b'\0'
    return struct.pack('<i', len(encoded)) + encoded


def pak_fixture(version=3, compressed=False, encrypted=False, name='asset.bin'):
    payload = '今日\n<color>学校</>（テスト）'.encode('utf-8')
    packed = zlib.compress(payload) if compressed else payload
    offset = 64
    header_size = 73 if compressed else 53
    block = header_size + (offset if version == 3 else 0)
    flags = int(encrypted)
    entry = struct.pack('<qqqI', offset, len(packed), len(payload), int(compressed))
    entry += hashlib.sha1(packed).digest()
    if compressed:
        entry += struct.pack('<iqq', 1, block, block + len(packed))
    entry += struct.pack('<BI', flags, 65536)
    key = bytes(range(32))  # synthetic fixture key only
    stored = packed
    if encrypted:
        stored += b'\0' * (-len(stored) % 16)
        stored = AES.new(key, AES.MODE_ECB).encrypt(stored)
    carrier = b'\0' * offset + entry + stored
    index = fstring('../../../') + struct.pack('<i', 1) + fstring(name) + entry
    if encrypted:
        index += b'\0' * (-len(index) % 16)
    digest = hashlib.sha1(index).digest()
    stored_index = AES.new(key, AES.MODE_ECB).encrypt(index) if encrypted else index
    footer = (b'\0' * 16 + bytes([encrypted])) if version == 8 else b''
    footer += struct.pack('<I i q q', 0x5A6F12E1, version, len(carrier), len(index)) + digest
    if version == 8:
        footer += b'Zlib' + b'\0' * 156
    return carrier + stored_index + footer, payload, key


def datatable_fixture():
    names = ['RowStruct', 'ObjectProperty', 'None', 'row_001', 'Character',
             'StrProperty', 'Japanese', 'TraditionalChinese']
    name_data = b''.join(fstring(n) + b'\0' * 4 for n in names)
    header = struct.pack('<Iiiiii', 0x9E2A83C1, -7, 0, 0, 0, 0)
    header += struct.pack('<i', 193 + len(name_data)) + fstring('None')
    header += struct.pack('<Iii', 0x80000000, len(names), 193)
    header = header.ljust(193, b'\0') + name_data
    fname = lambda name: struct.pack('<ii', names.index(name), 0)

    def prop(name, kind, data):
        return fname(name) + fname(kind) + struct.pack('<iiB', len(data), 0, 0) + data

    source = '今日は学校へ。\n<sprite name="a"/>名前{Player}'
    export = prop('RowStruct', 'ObjectProperty', struct.pack('<i', -1)) + fname('None')
    export += struct.pack('<ii', 0, 1) + fname('row_001')
    export += prop('Character', 'StrProperty', fstring('話者', wide=True))
    export += prop('Japanese', 'StrProperty', fstring(source, wide=True))
    export += prop('TraditionalChinese', 'StrProperty', fstring('別言語', wide=True))
    export += fname('None') + bytes.fromhex('c1832a9e')
    return header, export, source


class PakTests(unittest.TestCase):
    def test_stored_v3_and_zlib_relative_v8_are_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            for version, compressed, encrypted in [(3, False, False), (3, True, False),
                                                     (8, True, True), (8, False, True)]:
                with self.subTest(version=version, compressed=compressed, encrypted=encrypted):
                    data, expected, key = pak_fixture(version, compressed, encrypted)
                    path = Path(directory) / 'fixture.pak'
                    path.write_bytes(data)
                    pak = Pak(path, key if encrypted else None)
                    self.assertEqual(pak.read(pak.entries[0]), expected)
                    self.assertEqual(pak.mount, '../../../')

    def test_wrong_key_or_corrupt_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data, _, key = pak_fixture(8, True, True)
            path = Path(directory) / 'fixture.pak'
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'SHA1 mismatch'):
                Pak(path, bytes(reversed(key)))
            with self.assertRaisesRegex(ValueError, 'AES key required'):
                Pak(path)
            data, _, _ = pak_fixture()
            damaged = bytearray(data)
            damaged[-45] ^= 1
            path.write_bytes(damaged)
            with self.assertRaisesRegex(ValueError, 'SHA1 mismatch'):
                Pak(path)

    def test_archive_traversal_is_not_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, _, _ = pak_fixture(name='../outside.bin')
            path = root / 'fixture.pak'
            path.write_bytes(data)
            with patch('sys.argv', ['asset_extract.py', str(path), '--output', str(root / 'out')]):
                with self.assertRaisesRegex(ValueError, 'Unsafe PAK path'):
                    asset_extract.main()
            self.assertFalse((root / 'outside.bin').exists())


class DataTableTests(unittest.TestCase):
    def test_japanese_row_keeps_newlines_tags_and_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            asset, export, expected = datatable_fixture()
            path = Path(directory) / 'CML_test.uasset'
            path.write_bytes(asset)
            path.with_suffix('.uexp').write_bytes(export)
            rows = DataTable(path).rows()
            self.assertEqual(rows[0][0], 'row_001')
            self.assertEqual(rows[0][1]['Japanese'], expected)
            self.assertNotEqual(rows[0][1]['Japanese'], rows[0][1]['TraditionalChinese'])

    def test_unparsed_table_tail_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            asset, export, _ = datatable_fixture()
            path = Path(directory) / 'CML_test.uasset'
            path.write_bytes(asset)
            path.with_suffix('.uexp').write_bytes(export + b'junk')
            with self.assertRaisesRegex(ValueError, 'trailing export bytes'):
                DataTable(path).rows()


class LocResTests(unittest.TestCase):
    def test_compact_key_is_resolved_to_exact_japanese_string(self):
        entries = struct.pack('<iiI', 1, 1, 123) + fstring('namespace') + struct.pack('<iI', 1, 456)
        entries += fstring('name_key') + struct.pack('<Ii', 789, 0)
        offset = 25 + len(entries)
        header = bytes.fromhex('0e147475674a03fc4a15909dc3377f1b') + b'\x02' + struct.pack('<q', offset)
        strings = struct.pack('<i', 1) + fstring('名前', wide=True) + struct.pack('<i', 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.locres'
            path.write_bytes(header + entries + strings)
            result = read_locres(path)
            self.assertEqual(result, [{'namespace': 'namespace', 'key': 'name_key',
                                       'source_hash': 789, 'text': '名前'}])


if __name__ == '__main__':
    unittest.main()
