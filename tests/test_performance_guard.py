from pathlib import Path
import unittest

from lupa.lua54 import LuaRuntime
from test_dialogue import FIXTURE, NATIVE_FIXTURE

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/Scripts'


class PerformanceGuardTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            clock, scans, transitions = 0, 0, {}
            objects = {}
            function manager(id)
                return {alive=true,name='LiveManager /Game/Maps/LEVEL_Root.LEVEL_Root:PersistentLevel.LiveManager_'..id,
                    IsValid=function(self)return self.alive end,
                    GetAddress=function()return id end,GetFullName=function(self)return self.name end}
            end
            function FindAllOf(class)assert(class=='LiveManager');scans=scans+1;return objects end
            function NotifyOnNewObject(class,callback)assert(class=='/Script/imal.LiveManager');notify=callback end
            guard=require('performance_guard').new(function()return clock end,
                function(active)transitions[#transitions+1]=active end)
        ''')
        self.state = self.lua.globals()

    def test_existing_performance_is_detected_by_one_snapshot(self):
        self.lua.execute('objects={manager(1)};assert(guard:poll())')
        self.assertEqual(self.state.scans, 1)
        self.assertTrue(self.state.transitions[1])

    def test_construction_notification_does_not_read_uninitialized_fields(self):
        self.lua.execute('''
            assert(not guard:poll())
            live=manager(1)
            live.IsValid=function()error('still constructing')end
            notify(live)
            live.IsValid=function(self)return self.alive end
            clock=0.25;assert(guard:poll())
        ''')
        self.assertEqual(self.state.scans, 1)

    def test_inactive_ticks_and_long_performance_never_repeat_global_scans(self):
        self.lua.execute('''
            for i=1,1000 do clock=i/60;guard:poll() end
            live=manager(1);notify(live)
            for i=1001,10000 do clock=i/60;guard:poll() end
            assert(guard.active and #transitions==1)
        ''')
        self.assertEqual(self.state.scans, 1)

    def test_expiration_resumes_and_reused_address_can_start_another_mv(self):
        self.lua.execute('''
            live=manager(1);objects={live};assert(guard:poll())
            live.alive=false;clock=0.25;assert(not guard:poll())
            notify(manager(1));clock=0.5;assert(guard:poll())
            assert(#transitions==3 and transitions[2]==false)
        ''')

    def test_class_default_and_recycled_identity_cannot_keep_work_suspended(self):
        self.lua.execute('''
            live=manager(1);objects={live};assert(guard:poll())
            live.name='LiveManager /Script/imal.Default__LiveManager'
            clock=0.25;assert(not guard:poll())
            notify(live);clock=0.5;assert(not guard:poll())
        ''')

    def test_short_ticks_reuse_state_but_native_line_can_force_a_resume_check(self):
        self.lua.execute('''
            live=manager(1);objects={live};assert(guard:poll())
            live.alive=false;clock=0.01;assert(guard:poll())
            assert(not guard:poll(true))
        ''')


class PerformanceIntegrationTests(unittest.TestCase):
    def test_mv_bypasses_all_discovery_and_native_text_work_then_resumes(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute(FIXTURE + NATIVE_FIXTURE + '''
            test_clock,scan_count,ui_ticks=0,0,0
            local bridge=package.loaded.native_bridge.load()
            bridge.clock=function()return test_clock end
            local find=FindAllOf
            function FindAllOf(...)scan_count=scan_count+1;return find(...)end
            notifications,timers={},{}
            function NotifyOnNewObject(class,callback)notifications[class]=callback end
            function LoopInGameThreadWithDelay(ms,callback)timers[ms]=callback end
            package.loaded.ui_annotations={new=function()return {
                set_enabled=function(_,value)ui_enabled=value end,
                set_suspended=function(_,value)ui_suspended=value end,
                tick=function()ui_ticks=ui_ticks+1 end}end}
        ''')
        lua.execute("assert(load(..., '@D:/mod/Scripts/main.lua'))()", (SCRIPTS / 'main.lua').read_text(encoding='utf-8'))
        lua.execute('''
            test_text='school';StarlitFuriganaNativeLine(456,1,test_text)
            assert(test_updates==1)
            local live={alive=true,IsValid=function(self)return self.alive end,
                GetAddress=function()return 999 end,
                GetFullName=function()return 'LiveManager /Game/Maps/LEVEL_Root.LEVEL_Root:PersistentLevel.LiveManager_1' end}
            notifications['/Script/imal.LiveManager'](live)
            test_clock=1;timers[16]()
            assert(ui_suspended and test_detaches==1)
            local scans_before=scan_count
            for i=1,100 do
                test_clock=test_clock+0.02;timers[16]();timers[250]()
                StarlitFuriganaNativeLine(456,i+1,test_text)
                StarlitFuriganaNativeChoices()
            end
            assert(scan_count==scans_before and test_updates==1 and ui_ticks==0)
            assert(not StarlitFuriganaConsumeAdvance())
            live.alive=false;test_clock=test_clock+1;timers[16]()
            assert(not ui_suspended and ui_ticks==1 and ui_enabled)
            StarlitFuriganaNativeLine(456,200,test_text);assert(test_updates==2)
        ''')


if __name__ == '__main__':
    unittest.main()
