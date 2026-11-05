"""Regression coverage for the measured game-thread stalls and bounded state."""
from pathlib import Path
import unittest

from lupa.lua54 import LuaRuntime
import test_dialogue

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/Scripts'


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            scans, callbacks = 0, {}
            function object(address)
                return {alive=true, name='Synthetic'..address, IsValid=function(self) return self.alive end,
                    GetFullName=function(self) return self.name end,
                    GetAddress=function() return address end}
            end
            first=object(1)
            function FindAllOf(class)
                assert(class=='TextBlock'); scans=scans+1; return {first}
            end
            function NotifyOnNewObject(class, callback) callbacks[class]=callback end
            registry=require('object_registry').new({'/Script/UMG.TextBlock'})
        ''')
        self.state = self.lua.globals()

    def test_idle_does_not_repeat_global_discovery(self):
        self.lua.execute('for i=1,1000 do registry:objects() end')
        self.assertEqual(self.state.scans, 1)

    def test_live_notification_precedes_unfinished_initial_snapshot(self):
        self.lua.execute('''
            function FindAllOf() scans=scans+1;return {object(1),object(2),object(3),object(4)} end
            registry=require('object_registry').new({'/Script/UMG.TextBlock'},nil,{incremental=true,admit_limit=1})
            registry:take_new()
            later=object(99);callbacks['/Script/UMG.TextBlock'](later)
            assert(registry:take_new()[1]==later)
            assert(registry:take_new()[1]:GetAddress()==2)
        ''')

    def test_new_objects_after_initial_scan_are_found_without_rescanning(self):
        self.lua.execute('''
            registry:objects()
            later=object(2); callbacks['/Script/UMG.TextBlock'](later)
            found=registry:objects()[2]
        ''')
        self.assertTrue(self.lua.eval('found==later'))
        self.assertEqual(self.state.scans, 1)

    def test_notifications_do_not_read_uninitialized_fields(self):
        self.lua.execute('''
            later=object(2)
            later.IsValid=function() error('construction still running') end
            callbacks['/Script/UMG.TextBlock'](later)
            later.IsValid=function() return true end
            found=registry:objects()[2]
        ''')
        self.assertTrue(self.lua.eval('found==later'))

    def test_expired_objects_are_released_and_reused_addresses_replace_them(self):
        self.lua.execute('''
            registry:objects(); first.alive=false
            removed=registry:objects()[1]==nil
            replacement=object(1); callbacks['/Script/UMG.TextBlock'](replacement)
            replaced=registry:objects()[1]==replacement
        ''')
        self.assertTrue(self.state.removed)
        self.assertTrue(self.state.replaced)

    def test_reused_object_memory_is_rejected_without_a_new_notification(self):
        self.lua.execute("registry:objects(); first.name='DifferentObject'; removed=registry:objects()[1]==nil")
        self.assertTrue(self.state.removed)

    def test_native_event_before_notification_recovers_owner_once(self):
        self.lua.execute('''
            registry:objects()
            later=object(2)
            function FindAllOf() scans=scans+1; return {later} end
            recovered=registry:find(2)==later
            for i=1,100 do registry:find(2) end
        ''')
        self.assertTrue(self.state.recovered)
        self.assertEqual(self.state.scans, 2)


class NativePerformanceTests(unittest.TestCase):
    setUp = test_dialogue.NativeEventTests.setUp
    line = test_dialogue.NativeEventTests.line

    def test_queued_toggle_presses_keep_order_without_scheduling_from_input(self):
        self.line('学校')
        self.state.test_keys[118]()
        self.state.test_keys[118]()
        self.assertEqual(self.state.test_detaches, 0)
        self.state.test_loop()
        self.assertEqual(self.state.test_detaches, 1)
        self.assertEqual(self.state.test_updates, 2)

    def test_many_lines_and_idle_ticks_do_not_rescan_global_objects(self):
        self.lua.execute('''
            scan_count=0
            local find=FindAllOf
            function FindAllOf(...) scan_count=scan_count+1; return find(...) end
        ''')
        self.state.test_loop()
        initial = self.state.scan_count
        for generation in range(30):
            self.line('学校', generation + 1)
            self.state.test_loop()
        self.assertEqual(self.state.scan_count, initial)
        self.assertEqual(self.state.test_updates, 30)


class MeasurementTests(unittest.TestCase):
    def test_interrupted_long_page_finishes_without_repeating_completed_native_runs(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local renderer
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if name=='Renderer' then renderer=value end
            end
            local runs={}
            for i=1,40 do runs[i]={base=tostring(i),base_size=26,ruby_size=14,x=i,y=0} end
            local writes=0
            local r=setmetatable({widgets={},options={geometry=true,yield_work=function()error('defer')end},
                pages={{runs=runs}},active_margin={Left=0,Top=0},source_text='complete',
                _valid_source=function()return true end,
                parent={IsValid=function()return true end},
                host={SetVisibility=function()end,SetRenderOpacity=function()end},
                source={SetRenderOpacity=function()end},
                _set_text=function()writes=writes+1 end,
                _text_widget=function()return {SetVisibility=function()end},{SetPosition=function()end} end},renderer)
            local complete=false
            for attempt=1,41 do complete=pcall(r.show_page,r,1);if complete then break end end
            assert(complete and r.previous_text=='complete' and writes==40)
        ''')

    def test_ancestor_scale_animation_invalidates_ruby_font_compensation(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local renderer
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if name=='Renderer' then renderer=value end
            end
            local g={size={X=100,Y=40},scale={X=1,Y=1},absolute_scale=0.3}
            local r=setmetatable({options={geometry=function()return g end},
                parent={IsValid=function()return true end},_valid_source=function()return true end,
                _sync_slot=function()end},renderer)
            local animated=r:geometry_key()
            g.absolute_scale=1
            assert(animated~=r:geometry_key())
        ''')

    def test_native_widgets_reusing_generated_addresses_are_not_excluded(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local create
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if not name then break end
                if name=='create' then create=value end
            end
            local function object(name)
                return {name=name, IsValid=function() return true end,
                    GetAddress=function() return 1 end, GetFullName=function(self) return self.name end}
            end
            local made=object('Generated')
            function FName(name) return name end
            function made:GetFName() return {ToString=function() return self.name end} end
            function StaticConstructObject() return made end
            create({GetFullName=function() return 'SyntheticClass' end},nil)
            assert(ruby.is_generated(made))
            local native=object('Native')
            function native:GetFName() return {ToString=function() return self.name end} end
            assert(not ruby.is_generated(native))
            made.name='Native' -- An old wrapper can now refer to reused memory.
            assert(not ruby.is_generated(native))
        ''')

    def test_plain_runs_allocate_only_a_base_widget_and_reuse_the_pool(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local renderer
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if not name then break end
                if name=='Renderer' then renderer=value end
            end
            local created=0
            local r=setmetatable({widgets={},_text_widget=function()
                created=created+1; return {},{}
            end},renderer)
            local first=r:_pooled(1,nil); assert(created==1 and not first.ruby)
            assert(r:_pooled(1,nil)==first and created==1)
            assert(r:_pooled(1,'がっこう')==first and created==2 and first.ruby)
            r:_pooled(1,'がっこう'); assert(created==2)
        ''')

    def test_measurement_reuses_widths_separates_fonts_and_bounds_cache(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local renderer
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if not name then break end
                if name=='Renderer' then renderer=value end
            end
            assert(renderer)
            measurements=0
            local widget={SetVisibility=function() end, InvalidateLayoutAndVolatility=function() end,
                ForceLayoutPrepass=function() measurements=measurements+1 end,
                GetDesiredSize=function() return {X=20,Y=40} end}
            r=setmetatable({measure_widget=widget,widths={},width_keys={},width_cursor=1,heights={},
                _set_text=function() end}, renderer)
            r:_measure('学校',29,'base'); r:_measure('学校',29,'base')
            assert(measurements==1)
            r:_measure('学校',14,'ruby'); assert(measurements==2)
            for i=1,3000 do r:_measure(tostring(i),29,'base') end
            count=0; for _ in pairs(r.widths) do count=count+1 end
            assert(count==2048)
            r:_measure('学校',29,'base'); assert(measurements==3003)
        ''')


if __name__ == '__main__':
    unittest.main()
