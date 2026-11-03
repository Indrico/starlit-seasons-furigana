"""Cross-check release annotation lookup against Python's SHA-256 and UTF-8."""
import hashlib
import importlib.util
from pathlib import Path
import random
import tempfile
import unittest

from lupa.lua54 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('export_annotations', ROOT / 'tools/readings/export_annotations.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class ReadingLookupTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", (ROOT / 'mod/Scripts').as_posix())
        self.sha = self.lua.eval("(require('sha256'))")
        self.lookup = self.lua.eval("(require('reading_lookup'))")

    def load_database(self, records):
        database = export.annotations(records)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'readings.lua'
            export.write_lua(path, database)
            source = path.read_text(encoding='utf-8')
            return self.lua.execute(source), source

    def test_sha256_matches_standard_vectors_and_padding_boundaries(self):
        for text in ['', 'abc', '学校へ行く', '𠮷野\r\n今日', 'a' * 55, 'a' * 56,
                     'a' * 63, 'a' * 64, 'a' * 65, 'a' * 1000]:
            with self.subTest(text=text[:30]):
                self.assertEqual(self.sha.hex(text), hashlib.sha256(text.encode()).hexdigest())

    def test_sha256_matches_random_bytes(self):
        randomizer = random.Random(731)
        for _ in range(80):
            data = randomizer.randbytes(randomizer.randrange(0, 600))
            self.assertEqual(self.sha.hex(data), hashlib.sha256(data).hexdigest())

    def test_export_contains_only_hashes_spans_and_kana(self):
        text = '𠮷野は学校へ行く\r\n{PlayerName}'
        segments = [{'base': '𠮷野', 'reading': 'よしの'}, {'base': 'は'},
                    {'base': '学校', 'reading': 'がっこう'}, {'base': 'へ'},
                    {'base': '行', 'reading': 'い'}, {'base': 'く'},
                    {'base': '\r\n', 'control': True}, {'base': '{PlayerName}', 'control': True}]
        database, emitted = self.load_database([{'source_text': text, 'segments': segments}])
        for private in [text, '学校', '𠮷野', 'PlayerName']:
            self.assertNotIn(private, emitted)
        actual = self.lookup.get(database, text)
        decoded = [dict(segment.items()) for _, segment in actual.items()]
        self.assertEqual(decoded, segments)

    def test_changed_text_does_not_match_prebuilt_entry(self):
        database, _ = self.load_database([{'source_text': '学校', 'segments': [{'base': '学校', 'reading': 'がっこう'}]}])
        self.assertIsNone(self.lookup.get(database, '学枚'))
        self.assertIsNone(self.lookup.get(database, '学校\n'))

    def test_unannotated_rows_are_omitted_and_duplicates_share_one_entry(self):
        row = {'source_text': '学校', 'segments': [{'base': '学校', 'reading': 'がっこう'}]}
        data = export.annotations([row, row, {'source_text': 'はい', 'segments': [{'base': 'はい'}]}])
        self.assertEqual(len(data['entries']), 1)

    def test_invalid_span_keeps_native_text(self):
        database, _ = self.load_database([{'source_text': '学校', 'segments': [{'base': '学校', 'reading': 'がっこう'}]}])
        entry = database.entries[self.sha.hex('学校')]
        entry.s[1][1] = 2  # Splits a multibyte character.
        self.assertIsNone(self.lookup.get(database, '学校'))
        entry.s[1][1] = 100
        self.assertIsNone(self.lookup.get(database, '学校'))

    def test_export_rejects_non_kana_payload_and_mismatched_sources(self):
        for row in [{'source_text': '学校', 'segments': [{'base': '学校', 'reading': 'school'}]},
                    {'source_text': '学校', 'segments': [{'base': '違う', 'reading': 'ちがう'}]}]:
            with self.assertRaises(ValueError):
                export.annotations([row])


if __name__ == '__main__':
    unittest.main()
