"""Verify source selection and reveal gating without loading the game."""
from pathlib import Path
import unittest

from lupa.lua54 import LuaRuntime

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod' / 'Scripts'


FIXTURE = r'''
test_text = ''
test_name = 'RichTextBlock /Engine/Transient.GameEngine.WBP_Commu_Message_C_1:WidgetTree.RichTextBlock_Message'
test_short = 'RichTextBlock_Message'
test_generated = false
test_updates, test_hides, test_attaches, test_detaches = 0, 0, 0, 0
test_geometry = 'constant'
local source = {}
function source:IsValid() return true end
function source:GetAddress() return 123 end
function source:GetFullName() return test_name end
function source:GetFName() return {ToString = function() return test_short end} end
function source:GetText() return {ToString = function() return test_text end} end
local fake = {}
function fake.is_generated() return test_generated end
function fake.attach()
    test_attaches = test_attaches + 1
    local renderer = {}
    function renderer:geometry_key() return test_geometry end
    function renderer:update() test_updates = test_updates + 1; return true, {} end
    function renderer:hide() test_hides = test_hides + 1 end
    function renderer:detach() test_detaches = test_detaches + 1 end
    return renderer
end
package.loaded.umg_ruby = fake
function dofile() return {
    ['学校'] = {{base = '学校', reading = 'がっこう'}},
    ['はい'] = {{base = 'はい'}},
} end
function FindAllOf(name) return name == 'RichTextBlock' and {source} or {} end
function LoopInGameThreadWithDelay(_, callback) test_loop = callback end
function RegisterKeyBind(_, callback) test_toggle = callback end
Key = {F7 = 118}
function print() end
function test_step(text) test_text = text; test_loop() end
'''


class RuntimeGateTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute(FIXTURE)
        self.lua.execute("assert(load(..., '@D:/mod/Scripts/main.lua'))()",
                         (SCRIPTS / 'main.lua').read_text(encoding='utf-8'))
        self.state = self.lua.globals()

    def step(self, text):
        self.state.test_step(text)

    def test_only_exact_stable_text_is_rendered(self):
        self.step('学')
        self.step('学')
        self.assertEqual(self.state.test_updates, 0)
        self.step('学校')
        self.assertEqual(self.state.test_updates, 0)
        self.step('学校')
        self.assertEqual(self.state.test_updates, 1)

    def test_source_change_removes_previous_ruby_before_waiting(self):
        self.step('学校')
        self.step('学校')
        self.step('学')
        self.assertEqual(self.state.test_hides, 1)
        self.assertEqual(self.state.test_updates, 1)

    def test_unchanged_source_has_no_repeated_render_setters(self):
        for _ in range(5):
            self.step('学校')
        self.assertEqual(self.state.test_updates, 1)

    def test_toggle_off_detaches_renderer(self):
        self.step('学校')
        self.step('学校')
        self.state.test_toggle()
        self.step('学校')
        self.assertEqual(self.state.test_detaches, 1)
        self.assertEqual(self.state.test_updates, 1)

    def test_blueprint_templates_are_excluded(self):
        self.state.test_name = 'RichTextBlock /Game/WBP_Commu_Message.WBP_Commu_Message_C:WidgetTree.RichTextBlock_Message'
        self.step('学校')
        self.step('学校')
        self.assertEqual(self.state.test_attaches, 0)

    def test_generated_widgets_are_excluded(self):
        self.state.test_generated = True
        self.step('学校')
        self.step('学校')
        self.assertEqual(self.state.test_attaches, 0)

    def test_control_guide_labels_are_excluded(self):
        self.state.test_short = 'TextBlock_ControlGuide'
        self.step('学校')
        self.step('学校')
        self.assertEqual(self.state.test_attaches, 0)

    def test_kana_only_source_keeps_native_renderer(self):
        self.step('はい')
        self.step('はい')
        self.assertEqual(self.state.test_attaches, 0)


if __name__ == '__main__':
    unittest.main()
