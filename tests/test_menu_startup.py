"""Synthetic coverage for the master-menu input and startup flow boundary."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/Scripts'


class MenuStartupTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            function FindAllOf() return {} end
            function StaticFindObject()
                return {IsValid=function() return true end, Conv_StringToText=function(_, text) return text end}
            end
            visible, clicked, enabled = true, false, true
            settings = {enabled=true}
            owner = {IsValid=function() return true end, IsVisible=function() return visible end}
            button = {IsValid=function() return true end, GetOnClickedSignal=function() local was=clicked; clicked=false; return was end}
            label = {SetText=function(_, value) label_text=value end}
            menu = require('mod_menu').new(settings, function(value) enabled=value; settings.enabled=value end)
            menu.entries[1] = {owner=owner, button=button, label=label}
        ''')
        self.state = self.lua.globals()

    def test_menu_click_toggles_all_features_and_refreshes_label(self):
        self.lua.execute('clicked=true; menu:tick()')
        self.assertFalse(self.state.enabled)
        self.assertEqual(self.state.label_text, 'Furigana Mod: OFF  [F8]')
        self.lua.execute('clicked=true; menu:tick()')
        self.assertTrue(self.state.enabled)
        self.assertEqual(self.state.label_text, 'Furigana Mod: ON  [F8]')

    def test_hidden_menu_does_not_consume_click(self):
        self.lua.execute('visible=false; clicked=true; menu:tick()')
        self.assertTrue(self.state.enabled)

    def startup(self):
        self.lua.execute('''
            logo_index, opacity = 0, 1
            logo = {IsValid=function() return true end, GetAddress=function() return 10 end,
                SetRenderOpacity=function(_, value) opacity=value end,
                IsEndFlow=function() return logo_index >= 5 end,
                SetNextFlow=function() logo_index=logo_index+1 end}
            state = {Phase=2, WBP_Logo=logo, IsValid=function() return true end,
                GetFullName=function() return 'BP_TitleStateLogo_C /Game/Maps/LEVEL_Root:PersistentLevel.Logo' end}
            function FindAllOf() return {state} end
            startup = require('startup')
        ''')

    def test_startup_finishes_only_logo_flow_once(self):
        self.startup()
        self.lua.execute('startup.tick(true); startup.tick(true)')
        self.assertEqual(self.state.logo_index, 5)
        self.assertEqual(self.state.opacity, 0)
        self.assertEqual(self.state.state.Phase, 2)

    def test_startup_master_off_retains_native_logos(self):
        self.startup()
        self.lua.execute('startup.tick(false)')
        self.assertEqual(self.state.logo_index, 0)
        self.assertEqual(self.state.opacity, 1)

    def test_startup_handles_logo_flow_initializing_again(self):
        self.startup()
        self.lua.execute('state.Phase=1; startup.tick(true)')
        self.assertEqual(self.state.logo_index, 5)
        self.lua.execute('logo_index=0; state.Phase=2; startup.tick(true)')
        self.assertEqual(self.state.logo_index, 5)


if __name__ == '__main__':
    unittest.main()
