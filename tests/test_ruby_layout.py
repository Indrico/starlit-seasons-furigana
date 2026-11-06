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

    def test_overlay_does_not_widen_or_rewrap_native_text_for_long_readings(self):
        segments = self.lua.table_from([self.lua.table_from({'base': 'AB', 'reading': 'abcdefgh'}),
                                        self.lua.table_from({'base': 'C'})])
        result = self.layout.layout(segments, self.lua.table_from({
            'width': 60, 'measure': self.measure, 'base_size': 20, 'ruby_size': 14,
            'overlay_only': True, 'no_wrap': True, 'gap': -12}))
        self.assertEqual(result.lines, 1)
        self.assertEqual(result.runs[2].x, 40)
        self.assertEqual(result.runs[1].y, 0)
        self.assertEqual(result.runs[1].ruby_size, 14)

    def test_adjacent_overlay_readings_share_a_lane_without_moving_native_glyphs(self):
        segments = self.lua.table_from([self.lua.table_from({'base': 'AB', 'reading': 'abcd'}),
                                        self.lua.table_from({'base': 'CD', 'reading': 'efgh'})])
        result = self.layout.layout(segments, self.lua.table_from({
            'width': 80, 'measure': self.measure, 'base_size': 20, 'ruby_size': 14,
            'overlay_only': True, 'no_wrap': True}))
        self.assertEqual(len(result.runs), 1)
        self.assertEqual(result.runs[1].base, 'ABCD')
        self.assertEqual(result.runs[1].reading, 'abcdefgh')
        self.assertEqual(result.runs[1].x, 0)

    def test_reveal_never_shows_unrevealed_reading(self):
        result = self.run_layout([{'base': '学校', 'reading': 'がっこう'}], visible=1)
        self.assertEqual(result['runs'][1]['base'], '学')
        self.assertIsNone(result['runs'][1]['reading'])

    def test_nonwrapping_menu_measures_span_boundaries_instead_of_every_plain_character(self):
        self.lua.execute('calls=0')
        measure = self.lua.eval('function(text,size) calls=calls+1;return utf8.len(text)*size end')
        segments = self.lua.table_from([self.lua.table_from({'base': 'x' * 80}),
            self.lua.table_from({'base': 'AB', 'reading': 'abcdef'}), self.lua.table_from({'base': 'tail'})])
        result = self.layout.layout(segments, self.lua.table_from({'width': 2000,
            'measure': measure, 'base_size': 20, 'ruby_size': 10, 'overlay_only': True, 'no_wrap': True}))
        self.assertEqual(self.lua.globals().calls, 4)
        self.assertEqual(result.runs[2].x, 1600)
        self.assertEqual(result.line_widths[1], 1720)

    def test_nonwrapping_menu_chunks_preserve_crlf_and_native_justification(self):
        segments = self.lua.table_from([self.lua.table_from({'base': 'prefix\r\n'}),
            self.lua.table_from({'base': 'AB', 'reading': 'read'}), self.lua.table_from({'base': '\ntail'})])
        result = self.layout.layout(segments, self.lua.table_from({'width': 200,
            'measure': self.measure, 'base_size': 20, 'ruby_size': 10,
            'overlay_only': True, 'no_wrap': True, 'justification': 1}))
        self.assertEqual(result.lines, 3)
        self.assertEqual(result.runs[2].line, 2)
        self.assertEqual(result.runs[2].x, 80)

    def test_plain_log_runs_merge_without_moving_readings_or_crossing_lines(self):
        result = self.run_layout([{'base': 'abcdefgh'}, {'base': 'AB', 'reading': 'read'}, {'base': 'tail'}], width=120)
        old_reading = next(run for run in result.runs.values() if run.reading)
        old_x, old_y = old_reading.ruby_x, old_reading.ruby_y
        old_count = len(result.runs)
        result = self.layout.compact_plain(result, self.measure)
        self.assertLess(len(result.runs), old_count)
        merged_reading = next(run for run in result.runs.values() if run.reading)
        self.assertEqual((merged_reading.ruby_x, merged_reading.ruby_y), (old_x, old_y))
        self.assertEqual(result.runs[1].base, 'abcdef')

    def test_plain_log_compaction_rejects_a_kerning_change(self):
        result = self.run_layout([{'base': 'AV'}])
        kerned = self.lua.eval('function(text,size) return text=="AV" and 30 or utf8.len(text)*size end')
        result = self.layout.compact_plain(result, kerned)
        self.assertEqual(len(result.runs), 2)

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
