"""Run with a Lua 5.4 runtime provided by lupa; no game access is required."""
from pathlib import Path
import unittest

from lupa.lua54 import LuaRuntime

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod' / 'Scripts'


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.layout = self.lua.execute((SCRIPTS / 'ruby_layout.lua').read_text(encoding='utf-8'))
        self.measure = self.lua.eval('function(text, size) return utf8.len(text) * size end')

    def run_layout(self, parts, width=300, visible=None, justification=None):
        segments = self.lua.table_from([self.lua.table_from(part) for part in parts])
        opts = {'width': width, 'measure': self.measure, 'base_size': 20, 'ruby_size': 10}
        if visible is not None:
            opts['visible_count'] = visible
        if justification is not None:
            opts['justification'] = justification
        return self.layout.layout(segments, self.lua.table_from(opts))

    def test_ruby_is_above_base_and_centered(self):
        result = self.run_layout([{'base': '学校', 'reading': 'がっこう'}])
        run = result['runs'][1]
        self.assertLess(run['ruby_y'], run['y'])
        self.assertEqual(run['x'] + run['base_width'] / 2, run['ruby_x'] + run['ruby_width'] / 2)

    def test_reveal_never_shows_unrevealed_reading(self):
        result = self.run_layout([{'base': '学校', 'reading': 'がっこう'}], visible=1)
        self.assertEqual(result['runs'][1]['base'], '学')
        self.assertIsNone(result['runs'][1]['reading'])

    def test_reveal_does_not_change_word_position(self):
        parts = [{'base': '今日', 'reading': 'きょう'}, {'base': '学校', 'reading': 'がっこう'}]
        full, partial = self.run_layout(parts, width=60), self.run_layout(parts, width=60, visible=3)
        self.assertEqual(full['runs'][2]['x'], partial['runs'][2]['x'])
        self.assertEqual(full['runs'][2]['line'], partial['runs'][2]['line'])

    def test_crlf_is_one_line_break(self):
        result = self.run_layout([{'base': 'あ\r\nい'}])
        self.assertEqual(result['lines'], 2)
        self.assertEqual(result['runs'][2]['line'], 2)

    def test_line_breaks_never_enter_font_measurement(self):
        self.measure = self.lua.eval("function(text, size) assert(not text:find('[\\r\\n]')); return utf8.len(text) * size end")
        result = self.run_layout([{'base': 'あ\r\nい\nう'}])
        self.assertEqual(result['lines'], 3)

    def test_supplementary_character_is_one_character(self):
        result = self.run_layout([{'base': '𠮷田', 'reading': 'よしだ'}], visible=1)
        self.assertEqual(result['runs'][1]['base'], '𠮷')

    def test_closing_punctuation_stays_on_preceding_line(self):
        result = self.run_layout([{'base': 'あい。う'}], width=40)
        self.assertEqual(result['runs'][3]['line'], 1)
        self.assertEqual(result['runs'][4]['line'], 2)

    def test_opening_punctuation_moves_with_following_character(self):
        result = self.run_layout([{'base': 'あ「い'}], width=40)
        self.assertEqual(result['runs'][2]['line'], 2)
        self.assertEqual(result['runs'][3]['line'], 2)

    def test_center_justification_applies_to_both_base_and_ruby(self):
        result = self.run_layout([{'base': '学校', 'reading': 'がっこう'}], width=100, justification=1)
        run = result['runs'][1]
        self.assertEqual(run['x'] + run['base_width'] / 2, 50)
        self.assertEqual(run['ruby_x'] + run['ruby_width'] / 2, 50)

    def test_right_justification_uses_final_line_width_during_reveal(self):
        parts = [{'base': '学校', 'reading': 'がっこう'}]
        result = self.run_layout(parts, width=100, visible=1, justification=2)
        self.assertEqual(result['runs'][1]['x'], 60)


if __name__ == '__main__':
    unittest.main()
