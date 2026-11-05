"""Dialogue progression, pagination, preferences, and native-event integration."""
from pathlib import Path
import tempfile
import unittest

from lupa.lua54 import LuaRuntime

from test_runtime_gate import FIXTURE

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/Scripts'


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            calls = {held = 0, released = 0, manual = 0, auto = 0}
            bridge = {
                hold = function() calls.held = calls.held + 1 end,
                release = function() calls.released = calls.released + 1 end,
                manual = function() calls.manual = calls.manual + 1 end,
                auto = function() calls.auto = calls.auto + 1 end,
            }
            settings = {manual = true, auto_min_seconds = 3, auto_characters_per_second = 8}
            controller = require('dialogue_controller').new(bridge, settings)
            renderer = {page_index = 1, pages = {{base_text = '学校'}, {base_text = '次のページ'}}}
            function renderer:show_page(index) self.page_index = index end
        ''')
        self.state = self.lua.globals()

    def test_manual_wait_does_not_release_after_voice_duration(self):
        self.lua.execute("controller:set_line(renderer, '学校'); controller:tick(60)")
        self.assertEqual(self.state.calls.released, 0)
        self.assertEqual(self.state.renderer.page_index, 1)

    def test_one_input_advances_one_page_then_returns_to_native(self):
        self.lua.execute("controller:set_line(renderer, '学校')")
        self.assertTrue(self.state.controller.advance(self.state.controller))
        self.assertEqual(self.state.renderer.page_index, 2)
        self.assertFalse(self.state.controller.advance(self.state.controller))
        self.assertEqual(self.state.calls.released, 0)

    def test_auto_pages_wait_then_release_only_after_last_page(self):
        self.lua.execute("controller:set_line(renderer, '学校'); controller:set_manual(false); controller:tick(2.9)")
        self.assertEqual(self.state.renderer.page_index, 1)
        self.lua.execute('controller:tick(0.1)')
        self.assertEqual(self.state.renderer.page_index, 2)
        self.assertEqual(self.state.calls.released, 0)
        self.lua.execute('controller:tick(3); controller:tick(30)')
        self.assertEqual(self.state.calls.released, 1)

    def test_auto_reading_duration_accounts_for_long_text(self):
        self.lua.execute("controller:set_line(nil, string.rep('あ', 40)); controller:set_manual(false); controller:tick(3)")
        self.assertEqual(self.state.calls.released, 0)
        self.lua.execute('controller:tick(2)')
        self.assertEqual(self.state.calls.released, 1)

    def test_mode_change_resets_page_timer_and_persists_setting(self):
        self.lua.execute("controller:set_line(renderer, '学校'); controller:set_manual(false); controller:tick(2); controller:set_manual(true); controller:tick(30)")
        self.assertTrue(self.state.settings.manual)
        self.assertEqual(self.state.renderer.page_index, 1)
        self.lua.execute('controller:set_manual(false); controller:tick(2)')
        self.assertEqual(self.state.renderer.page_index, 1)

    def test_clear_removes_stale_pagination(self):
        self.lua.execute("controller:set_line(renderer, '学校'); controller:clear(); controller:set_manual(false); controller:tick(60)")
        self.assertFalse(self.state.controller.advance(self.state.controller))
        self.assertEqual(self.state.calls.released, 0)

    def test_pagination_preserves_ruby_groups_sizes_and_order(self):
        self.lua.execute('''
            local layout = require('ruby_layout')
            local input = {{base='学校',reading='がっこう'},{base='へ行く。次の日も学校へ行く。'}}
            result = layout.layout(input, {width=90,base_size=29,ruby_size=14,
                base_height=40,ruby_height=20,gap=2,line_gap=2,
                measure=function(text,size) return utf8.len(text)*size end})
            pages = assert(layout.paginate(result, 126))
        ''')
        self.assertGreater(len(self.state.pages), 1)
        text = ''
        for page in self.state.pages.values():
            self.assertLessEqual(page.height, 126)
            for run in page.runs.values():
                self.assertEqual(run.base_size, 29)
                self.assertEqual(run.ruby_size, 14)
                self.assertGreaterEqual(run.ruby_y, 0)
                text += run.base
        self.assertEqual(text, '学校へ行く。次の日も学校へ行く。')
        self.assertEqual(self.state.pages[1].runs[1].reading, 'がっこう')

    def test_too_short_page_is_rejected_without_shrinking(self):
        self.lua.execute('''
            result = require('ruby_layout').layout({{base='学校',reading='がっこう'}},
                {width=300,base_size=29,ruby_size=14,base_height=40,ruby_height=20,
                 measure=function(text,size) return utf8.len(text)*size end})
        ''')
        pages, reason = self.lua.eval("require('ruby_layout').paginate")(self.state.result, 30)
        self.assertIsNone(pages)
        self.assertIn('fixed font', reason)

    def test_preferences_round_trip_and_invalid_values_do_not_execute(self):
        module = self.lua.eval("(require('settings'))")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'user-settings.ini'
            values = module.load(str(path))
            self.assertTrue(values.manual)
            values.manual = False
            result = module.save(str(path), values)
            self.assertTrue(result[0] if isinstance(result, tuple) else result)
            self.assertFalse(module.load(str(path)).manual)
            path.write_text('manual = invalid\nauto_min_seconds = -10\nauto_characters_per_second = math.huge\n', encoding='utf-8')
            values = module.load(str(path))
            self.assertTrue(values.manual)
            self.assertEqual(values.auto_min_seconds, 3)
            self.assertEqual(values.auto_characters_per_second, 8)


NATIVE_FIXTURE = r'''
test_keys, test_options = {}, nil
function RegisterKeyBind(key, callback) test_keys[key] = callback end
Key.F6 = 117
function ExecuteInGameThreadWithDelay(_, callback) callback() end
local old_find = FindAllOf
local owner = {_TextMessage=source}
function owner:IsValid() return true end
function owner:IsA() return true end
function owner:GetAddress() return 456 end
function owner:GetFullName() return 'WidgetCommuScriptMessage /Engine/Transient.SyntheticOwner' end
function FindAllOf(name) return name == 'WidgetCommuScriptMessage' and {owner} or old_find(name) end
package.loaded.settings = {
    load=function() return {manual=true,auto_min_seconds=3,auto_characters_per_second=8} end,
    save=function() test_saved=true; return true end,
}
local bridge = {manual=function() end, auto=function() end, hold=function() end, release=function() end,
    enable=function() test_bridge_enabled=true end, disable=function() test_bridge_enabled=false end}
bridge.initialize=function() StarlitFuriganaNativeReady() end
package.loaded.native_bridge = {load=function() return bridge end}
local attach = package.loaded.umg_ruby.attach
package.loaded.umg_ruby.attach=function(source, options)
    test_options=options
    local renderer=attach(source,options)
    renderer.pages={{base_text='学校'}}
    renderer.page_index=1
    function renderer:show_page(index) self.page_index=index end
    return renderer
end
'''


class NativeEventTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute(FIXTURE + NATIVE_FIXTURE)
        self.lua.execute("assert(load(..., '@D:/mod/Scripts/main.lua'))()", (SCRIPTS / 'main.lua').read_text(encoding='utf-8'))
        self.state = self.lua.globals()

    def line(self, text, generation=1):
        self.state.test_text = text
        self.state.StarlitFuriganaNativeLine(456, generation, text)

    def test_complete_line_renders_on_first_event(self):
        self.line('学校')
        self.assertEqual(self.state.test_updates, 1)
        self.assertTrue(self.state.test_options.fixed_size)
        self.assertEqual(self.state.test_options.fixed_base_size, 29)
        self.assertTrue(self.state.test_options.expand_dialogue)

    def test_repeated_identical_line_has_a_new_generation(self):
        self.line('学校')
        self.line('学校', 2)
        self.assertEqual(self.state.test_updates, 2)

    def test_kana_only_line_uses_the_same_fixed_layout(self):
        self.line('はい')
        self.assertEqual(self.state.test_updates, 1)
        self.assertEqual(self.state.test_options.fixed_base_size, 29)

    def test_native_clear_restores_previous_renderer(self):
        self.line('学校')
        self.state.StarlitFuriganaNativeClear()
        self.assertEqual(self.state.test_hides, 1)

    def test_f6_saves_mode_and_f7_remains_independent(self):
        self.state.test_keys[117]()
        self.assertIsNone(self.state.test_saved)
        self.state.test_loop()
        self.assertTrue(self.state.test_saved)
        self.line('学校')
        self.state.test_keys[118]()
        self.state.test_loop()
        self.assertEqual(self.state.test_detaches, 1)

    def test_master_off_restores_text_and_blocks_native_line_rendering(self):
        self.line('学校')
        self.state.StarlitFuriganaSetEnabled(False)
        self.assertFalse(self.state.test_bridge_enabled)
        self.assertEqual(self.state.test_detaches, 1)
        self.line('学校', 2)
        self.assertEqual(self.state.test_updates, 1)

    def test_master_on_restores_bridge_and_manual_preference(self):
        self.state.StarlitFuriganaSetEnabled(False)
        self.state.StarlitFuriganaSetEnabled(True)
        self.assertTrue(self.state.test_bridge_enabled)
        self.line('学校')
        self.assertEqual(self.state.test_updates, 1)


if __name__ == '__main__':
    unittest.main()
