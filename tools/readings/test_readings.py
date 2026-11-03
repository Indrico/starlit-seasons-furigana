import json
from pathlib import Path
import tempfile
import unittest

from generate import Annotator, align, build, lua_string


class FuriganaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overrides = json.loads(Path(__file__).with_name("overrides.json").read_text(encoding="utf-8"))
        cls.annotator = Annotator(cls.overrides)

    def readings(self, text):
        segments, issues = self.annotator.annotate(text)
        self.assertEqual("".join(s["base"] for s in segments), text)
        return {s["base"]: s["reading"] for s in segments if "reading" in s}, issues

    def test_contextual_compound_readings(self):
        readings, issues = self.readings("今日は大人が学校へ行った。")
        self.assertEqual(readings["今日"], "きょう")
        self.assertEqual(readings["大人"], "おとな")
        self.assertEqual(readings["学校"], "がっこう")
        self.assertFalse(issues)

    def test_okurigana_is_not_ruby(self):
        self.assertEqual(align("食べ物", "タベモノ"), [{"base": "食", "reading": "た"}, {"base": "べ"}, {"base": "物", "reading": "もの"}])
        readings, issues = self.readings("食べた物を取り戻したい。")
        self.assertEqual(readings["食"], "た")
        self.assertEqual(readings["物"], "もの")
        self.assertFalse(issues)

    def test_controls_and_placeholders_are_preserved(self):
        text = '<color value="赤">学校</>\n{PlayerName}と食べる。\\n%1$s'
        segments, _ = self.annotator.annotate(text)
        self.assertEqual("".join(s["base"] for s in segments), text)
        controls = [s["base"] for s in segments if s.get("control")]
        self.assertEqual(controls, ['<color value="赤">', '</>', '\n', '{PlayerName}', '\\n', '%1$s'])
        self.assertFalse(any(s.get("reading") for s in segments if s.get("control")))

    def test_names_and_unrelated_kanji_are_not_confused(self):
        readings, _ = self.readings("奥空心白と真が学校へ行く。")
        self.assertEqual(readings["奥空心白"], "おくぞらこはく")
        self.assertEqual(readings["真"], "まこと")
        # Matching the name token must not turn 真っ赤 into まことっあか.
        segments, _ = self.annotator.annotate("真っ赤")
        self.assertFalse(any(s.get("reading") == "まこと" for s in segments))

    def test_small_katakana_inside_proper_name(self):
        readings, issues = self.readings("城ヶ崎美嘉")
        self.assertEqual(readings["城ヶ崎美嘉"], "じょうがさきみか")
        self.assertFalse(issues)

    def test_standalone_given_names(self):
        for name, expected in self.overrides["tokens"].items():
            with self.subTest(name=name):
                segments, issues = self.annotator.annotate(name)
                self.assertEqual("".join(s.get("reading", s["base"]) for s in segments), expected)
                self.assertFalse(issues)

    def test_common_pronoun_override_does_not_rewrite_compounds(self):
        readings, issues = self.readings("私は私立の学校へ行く。")
        self.assertEqual(readings["私"], "わたし")
        self.assertEqual(readings["私立"], "しりつ")
        self.assertFalse(issues)

    def test_reunion_today_uses_exact_source_override_only(self):
        text = "ふふっ。それで、今日再会して……どうですか？\n私、変わりました？"
        readings, issues = self.readings(text)
        self.assertEqual(readings["今日"], "きょう")
        self.assertFalse(issues)
        # A formal-context line must retain the tokenizer's own decision.
        other = "今日に至るまで、学校は変わらない。"
        baseline = Annotator({**self.overrides, "source_tokens": {}})
        self.assertEqual(self.annotator.annotate(other), baseline.annotate(other))

    def test_supplementary_unicode_is_preserved_and_reported(self):
        text = "𠮷𰀀😀学校\r\n"
        segments, issues = self.annotator.annotate(text)
        self.assertEqual("".join(s["base"] for s in segments), text)
        self.assertTrue(any("𰀀" in issue["surface"] for issue in issues))

    def test_lua_control_escaping(self):
        self.assertEqual(lua_string('a\n1"\\'), '"a\\0101\\"\\\\"')

    def test_build_deduplicates_without_losing_provenance(self):
        source = "学校"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            coverage = build([{"asset": "a", "row_id": "1", "source_text": source}, {"asset": "b", "row_id": "2", "source_text": source}], output, self.overrides)
            self.assertEqual(coverage["input_records"], 2)
            self.assertEqual(coverage["unique_source_texts"], 1)
            data = json.loads((output / "readings.json").read_text(encoding="utf-8"))
            self.assertEqual([record["asset"] for record in data], ["a", "b"])
            self.assertEqual(len(data[0]["source_sha256"]), 64)
            self.assertIn("がっこう", (output / "readings.lua").read_text(encoding="utf-8"))
            self.assertEqual(coverage["manually_reviewed_records"], 0)


if __name__ == "__main__":
    unittest.main()
