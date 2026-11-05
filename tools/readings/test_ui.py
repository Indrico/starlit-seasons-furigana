import hashlib
import tempfile
from pathlib import Path
import unittest

from build_ui import character_readings, image_bindings, prepare, write_bindings
from generate import Annotator


class UIReadingTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [{'row_id': 'synthetic01', 'Kan_Full': '山田 真', 'Ruby': 'やまだ\u3000まこと'},
                         {'row_id': 'unknown', 'Kan_Full': '未知 名前', 'Ruby': ''}]

    def test_official_names_include_spacing_and_short_aliases(self):
        names, aliases = character_readings(self.profiles, {})
        self.assertEqual(names, {'synthetic01': 'やまだまこと'})
        self.assertEqual(aliases['山田真'], 'やまだまこと')
        self.assertEqual(aliases['山田\u3000真'], 'やまだ\u3000まこと')
        self.assertEqual(aliases['真'], 'まこと')
        self.assertNotIn('未知 名前', aliases)

    def test_exact_alias_does_not_rewrite_unrelated_compound(self):
        records, overrides, _ = prepare([], [{'text': '設定'}], self.profiles, {})
        annotator = Annotator(overrides)
        self.assertEqual(annotator.annotate('真')[0], [{'base': '真', 'reading': 'まこと'}])
        self.assertFalse(any(s.get('reading') == 'まこと' for s in annotator.annotate('真っ赤')[0]))
        self.assertIn({'source_text': '設定'}, records)

    def test_unspaced_verified_override_splits_using_verified_given_name(self):
        names, aliases = character_readings([{'row_id': 'a', 'Kan_Full': '山田 真'}],
            {'phrases': {'山田真': 'やまだまこと'}, 'tokens': {'真': 'まこと'}})
        self.assertEqual(aliases['山田'], 'やまだ')

    def test_binding_export_contains_no_names_paths_or_row_id(self):
        names, aliases = character_readings(self.profiles, {})
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'bindings.lua'
            write_bindings(target, image_bindings(names), aliases)
            text = target.read_text(encoding='utf-8')
        self.assertNotIn('山田', text)
        self.assertNotIn('synthetic01', text)
        self.assertNotIn('WDT_name', text)
        self.assertIn('やまだまこと', text)
        self.assertIn(hashlib.sha256('真'.encode()).hexdigest(), text)

    def test_conflicting_short_name_stays_unannotated(self):
        profiles = [{'row_id': 'a', 'Kan_Full': '甲 真', 'Ruby': 'こう まこと'},
                    {'row_id': 'b', 'Kan_Full': '乙 真', 'Ruby': 'おつ しん'}]
        _, aliases = character_readings(profiles, {})
        self.assertNotIn('真', aliases)
        self.assertEqual(aliases['甲 真'], 'こう まこと')

    def test_image_coordinates_reject_non_numeric_non_finite_and_reversed_bounds(self):
        names={'synthetic01':'やまだ'}
        key=next(iter(image_bindings(names)))
        for bounds in ({'left':'0;code()'}, {'left':float('nan')}, {'left':0.8,'right':0.2}):
            with self.assertRaises(ValueError):
                image_bindings(names,{key:bounds})


if __name__ == '__main__':
    unittest.main()
