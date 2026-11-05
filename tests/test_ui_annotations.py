from pathlib import Path
import unittest

from lupa.lua54 import LuaRuntime

SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/Scripts'


class UIAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            clock=0
            scans, updates, detaches, hides = 0, 0, 0, 0
            notifications, objects = {}, {}
            function source(id)
                local w={alive=true,text='学校',RenderOpacity=1,name='TextBlock /Engine/Transient.WBP_Test_C.'..id}
                w.Font={Size=26,OutlineSettings={OutlineSize=0}}
                w.ColorAndOpacity={SpecifiedColor={R=1,G=1,B=1,A=1}}
                function w:IsValid() return self.alive end
                function w:GetAddress() return id end
                function w:GetFullName() return self.name end
                function w:GetFName() return {ToString=function() return 'Text' end} end
                function w:GetText() return {ToString=function() return self.text end} end
                function w:GetParent() return nil end
                function w:GetOuter() return nil end
                function w:IsVisible() return true end
                function w:IsA(class) return class=='/Script/UMG.TextBlock' end
                return w
            end
            objects[1]=source(1)
            function NotifyOnNewObject(class, callback) notifications[class]=callback end
            function FindAllOf(class) scans=scans+1; return class=='TextBlock' and objects or {} end
            local parent={IsValid=function() return true end,IsA=function(_,class) return class=='/Script/UMG.CanvasPanel' end,
                IsVisible=function() return true end, RenderOpacity=1}
            package.loaded.umg_ruby={
                is_generated=function(w) return w.generated end,
                parent_of=function(w) if w==parent then return nil end; return parent end,
                attach=function(w,options)
                    assert(options.min_ruby_size==(expected_min or 11) and options.fixed_size and options.overlay_only)
                    last_options=options
                    return {options=options,geometry_key=function() return 'fixed' end,
                        update=function() updates=updates+1; return true end,
                        hide=function() hides=hides+1 end,detach=function() detaches=detaches+1 end}
                end}
            package.loaded.ui_geometry={new=function() return {begin_frame=function() end,
                relative=function() return {size={X=200,Y=50}} end} end}
            module=require('ui_annotations')
            ui=module.new({['学校']={{base='学校',reading='がっこう'}},['名前']={{base='名前',reading='なまえ'}}},{clock=function()return clock end},{},function() end)
            function test_tick() clock=clock+0.3;ui:tick() end
        ''')
        self.state = self.lua.globals()

    def test_text_change_removes_stale_ruby_and_keeps_independent_progression(self):
        self.lua.execute("test_tick(); objects[1].text='名前'; ui:changed(objects[1])")
        self.assertGreater(self.state.hides, 0)
        self.lua.execute('test_tick()')
        self.assertEqual(self.state.updates, 2)

    def test_toggle_off_and_on_reuses_discovered_sources(self):
        self.lua.execute('test_tick(); ui:set_enabled(false); test_tick()')
        self.assertEqual(self.state.detaches, 1)
        self.assertEqual(self.state.updates, 1)
        self.lua.execute('ui:set_enabled(true); test_tick()')
        self.assertEqual(self.state.updates, 2)
        self.assertEqual(self.state.scans, 3)

    def test_idle_and_notifications_never_repeat_global_scans(self):
        self.lua.execute('''
            test_tick()
            for i=1,100 do test_tick() end
            later=source(2); notifications['/Script/UMG.TextBlock'](later); test_tick()
        ''')
        self.assertEqual(self.state.scans, 3)
        self.assertEqual(self.state.updates, 2)

    def test_recycled_object_identity_drops_its_old_overlay(self):
        self.lua.execute("test_tick(); objects[1].name='Other object'; test_tick()")
        self.assertEqual(self.state.detaches, 1)
        self.assertTrue(self.lua.eval('ui.entries[1]==nil'))

    def test_unknown_replacement_restores_native_text(self):
        self.lua.execute("test_tick(); objects[1].text='unmatched'; test_tick()")
        self.assertGreater(self.state.hides, 0)
        self.assertEqual(self.state.updates, 1)

    def test_measurement_lookup_cache_is_bounded(self):
        self.lua.execute("for i=1,5000 do ui:segments('synthetic'..i) end")
        self.assertLessEqual(self.lua.eval('(function() local n=0;for _ in pairs(ui.lookup)do n=n+1 end;return n end)()'), 2048)

    def test_generated_sources_and_lyric_widgets_are_excluded(self):
        self.lua.execute("objects[1].generated=true")
        self.assertFalse(self.state.module.eligible(self.state.objects[1]))
        self.lua.execute("objects[1].generated=false;objects[1].name='TextBlock /Engine/Transient.WBP_Lyric_C'")
        self.assertFalse(self.state.module.eligible(self.state.objects[1]))

    def test_person_name_keeps_larger_reading_than_menu(self):
        self.lua.execute('''
            expected_min=14
            objects[1].name='TextBlock /Engine/Transient.WBP_Commu_MessageName.charaname_text'
            ui.bindings.names={[require('sha256').hex(objects[1].text)]=true}
            test_tick()
        ''')
        self.assertEqual(self.state.last_options.min_ruby_size, 14)
        self.assertEqual(self.state.last_options.ruby_scale, 0.5)

    def test_inactive_screen_does_not_poll_its_text(self):
        self.lua.execute('''
            root={active=false,RenderOpacity=1,IsValid=function()return true end,IsVisible=function()return true end,
                GetAddress=function()return 900 end,GetFullName=function()return 'screen' end,
                IsInViewport=function(self)return self.active end,IsA=function(_,class)return class=='/Script/UMG.UserWidget' end}
            package.loaded.umg_ruby.parent_of=function(w) if w==root then return nil end;return root end
            reads=0
            objects[1].GetText=function(self) reads=reads+1;return {ToString=function()return self.text end} end
            for i=1,100 do test_tick() end
        ''')
        self.assertEqual(self.state.reads, 0)

    def test_existing_overlays_leave_time_for_newly_visible_sources(self):
        self.lua.execute('''
            test_tick()
            for id=2,30 do
                local w=source(id)
                w.GetFullName=function(self) clock=clock+0.0003;return self.name end
                ui.active[id]={source=w,name=w.name,renderer={detach=function()end},next_poll=0}
            end
            local inspect=ui.inspect
            ui.inspect=function(self,entry,deadline)
                local id=entry.source:GetAddress()
                if id>1 and id<100 then return end
                return inspect(self,entry,deadline)
            end
            later=source(100)
            notifications['/Script/UMG.TextBlock'](later)
            for i=1,10 do test_tick() end
        ''')
        self.assertTrue(self.lua.eval('ui.entries[100].applied'))

    def test_preparation_spans_ticks_and_toggle_cancels_partial_work(self):
        self.lua.execute('''
            local attach=package.loaded.umg_ruby.attach
            package.loaded.umg_ruby.attach=function(w,options)
                local renderer=attach(w,options)
                local prepared=0
                renderer.update=function()
                    while prepared<20 do prepared=prepared+1;options.yield_work() end
                    updates=updates+1;return true
                end
                return renderer
            end
            local elapsed=0
            ui=module.new({[objects[1].text]={{base=objects[1].text,reading='a'}}},
                {clock=function() elapsed=elapsed+0.001;return elapsed end},{},function()end)
            test_tick()
        ''')
        self.assertEqual(self.state.updates, 0)
        self.assertTrue(self.lua.eval('ui.work~=nil'))
        self.lua.execute('ui:set_enabled(false);for i=1,30 do test_tick() end')
        self.assertEqual(self.state.updates, 0)
        self.lua.execute('ui:set_enabled(true);for i=1,30 do test_tick() end')
        self.assertEqual(self.state.updates, 1)

    def test_changed_text_cancels_a_suspended_layout(self):
        self.lua.execute('''
            local attach=package.loaded.umg_ruby.attach
            applied={}
            package.loaded.umg_ruby.attach=function(w,options)
                local renderer=attach(w,options)
                local prepared={}
                renderer.update=function(_,segments)
                    local key=segments[1].base
                    while (prepared[key] or 0)<10 do prepared[key]=(prepared[key] or 0)+1;options.yield_work() end
                    applied[#applied+1]=segments[1].base;return true
                end
                return renderer
            end
            local elapsed=0
            ui=module.new({['old']={{base='old',reading='a'}},['new']={{base='new',reading='b'}}},
                {clock=function()elapsed=elapsed+0.001;return elapsed end},{},function()end)
            objects[1].text='old';test_tick()
            objects[1].text='new';ui:changed(objects[1])
            for i=1,30 do test_tick() end
        ''')
        self.assertEqual(list(self.state.applied.values()), ['new'])

    def test_hundred_sources_scroll_and_thirty_reopens_bound_live_renderers(self):
        self.lua.execute('''
            objects={};live=0
            for i=1,100 do
                local w=source(i);w.shown=i<=5
                w.IsVisible=function(self)return self.shown end
                objects[i]=w
            end
            local attach=package.loaded.umg_ruby.attach
            package.loaded.umg_ruby.attach=function(w,options)
                local renderer=attach(w,options);live=live+1
                renderer.detach=function(self)
                    if not self.detached then self.detached=true;live=live-1 end
                end
                return renderer
            end
            for i=1,20 do test_tick() end
            for first=1,96,5 do
                for i,w in ipairs(objects) do w.shown=i>=first and i<first+5 end
                for i=1,5 do test_tick() end
                assert(live==5)
            end
            for i=1,30 do
                ui:set_enabled(false);assert(live==0)
                ui:set_enabled(true);test_tick();assert(live==5)
            end
            assert(#ui.order==100 and scans==3)
        ''')


class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            next_id=0
            function widget(height,y)
                next_id=next_id+1;local id=next_id
                local slot={x=10,y=y or 84,width=950,height=height or 120}
                function slot:IsValid()return true end
                function slot:IsA(c)return c=='/Script/UMG.CanvasPanelSlot' end
                function slot:GetAddress()return id end
                function slot:GetFullName()return 'Slot'..id end
                function slot:GetPosition()return {X=self.x,Y=self.y} end
                function slot:GetSize()return {X=self.width,Y=self.height} end
                function slot:SetPosition(p)self.x,self.y=p.X,p.Y end
                function slot:SetSize(s)self.width,self.height=s.X,s.Y end
                return {Slot=slot,IsValid=function()return true end,GetParent=function()return nil end}
            end
            node={GetAddress=function()return 999 end,GetFullName=function()return 'NativeLogNode' end,
                IsValid=function()return true end,InvalidateLayoutAndVolatility=function()end,
                _TextSelectMessage=widget(),_TextNonSelectMessage=widget(),
                _TextSelectName=widget(38,12),_TextNonSelectName=widget(38,12),
                _PanelSelectDefault=widget(204,0),_PanelNonSelectDefault=widget(204,0),HitArea=widget(204,0)}
            backlog=require('backlog').new()
            description={node=node,message=true,mini=false}
        ''')

    def test_selected_and_unselected_cards_reserve_the_same_height(self):
        self.lua.execute('backlog:grow(description,160)')
        self.assertEqual(self.lua.eval('node._PanelSelectDefault.Slot.height'), 260)
        self.assertEqual(self.lua.eval('node._PanelNonSelectDefault.Slot.height'), 260)
        self.assertEqual(self.lua.eval('node.HitArea.Slot.height'), 204)
        self.assertEqual(self.lua.eval('node._TextSelectName.Slot.y'), 28)

    def test_repeated_grow_is_idempotent_and_off_restores_native_dimensions(self):
        self.lua.execute('backlog:grow(description,160);backlog:grow(description,160);backlog:grow(description,100)')
        self.assertEqual(self.lua.eval('node._PanelSelectDefault.Slot.height'), 260)
        self.lua.execute('backlog:clear()')
        self.assertEqual(self.lua.eval('node._PanelSelectDefault.Slot.height'), 204)
        self.assertEqual(self.lua.eval('node._TextSelectName.Slot.y'), 12)
        self.assertEqual(self.lua.eval('node._TextSelectMessage.Slot.height'), 120)

    def test_hundred_row_log_keeps_only_viewport_and_one_row_buffer(self):
        self.lua.execute('''
            rows={};reads=0
            scroll={IsValid=function()return true end,IsA=function(_,class)return class=='/Script/UMG.ScrollBox' end,
                GetAddress=function()return 800 end,GetFullName=function()return 'Scroll' end,
                GetScrollOffset=function()return 49*240 end,GetScrollOffsetOfEnd=function()return 100*240-600 end,
                GetChildrenCount=function()return 100 end,
                GetChildAt=function(_,i)reads=reads+1;return rows[i+1] end}
            for i=1,100 do
                local id=i
                rows[i]={IsValid=function()return true end,GetAddress=function()return id end,
                    GetParent=function()return scroll end,GetVisibility=function()return 0 end,
                    GetDesiredSize=function()return {Y=240} end,Slot={Padding={Top=0,Bottom=0}}}
            end
            -- Every cached painted position is stale and appears on screen.
            geometry={read=function()return {1142,600} end,
                relative=function()return {position={Y=0},size={Y=240},scale={Y=1}} end}
            description.node=rows[1]
            for i=1,13 do
                backlog:begin_frame();local before=reads;backlog:in_range(description,geometry)
                assert(reads-before<=8)
            end
            count=0
            for i=1,100 do
                description.node=rows[i]
                if backlog:in_range(description,geometry) then count=count+1 end
            end
            description.node=rows[1];assert(backlog:in_range(description,geometry)==false)
            description.node=rows[100];assert(backlog:in_range(description,geometry)==false)
        ''')
        self.assertLessEqual(self.lua.globals().count, 6)

    def test_growing_cards_keeps_the_bottom_only_when_already_at_the_end(self):
        self.lua.execute('''
            bottom_calls=0;offset=200
            local scroll={IsValid=function()return true end,GetAddress=function()return 800 end,
                GetFullName=function()return 'Scroll' end,
                IsVisible=function()return true end,GetScrollOffset=function()return offset end,
                ScrollToEnd=function()bottom_calls=bottom_calls+1 end}
            description.scroll=scroll
            backlog.scrolls[800]={owner=scroll,name='Scroll',at_end=false,offset=offset}
            backlog:grow(description,140)
            assert(bottom_calls==0)
            backlog.scrolls[800].at_end=true
            backlog:grow(description,160)
            assert(bottom_calls==0)
            backlog:begin_frame();backlog:begin_frame()
            assert(bottom_calls==1)
            backlog:grow(description,160)
            assert(bottom_calls==1)
            backlog:grow(description,180)
            offset=100 -- User scrolls upward before the pending layout pass.
            backlog:begin_frame();backlog:begin_frame()
            assert(bottom_calls==1)
        ''')


class OverlayLayoutTests(unittest.TestCase):
    def test_padded_overlay_does_not_inflate_native_canvas_desired_size(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        lua.execute('''
            local ruby=require('umg_ruby')
            local overlay_canvas, renderer
            for i=1,100 do
                local name,value=debug.getupvalue(ruby.attach,i)
                if name=='overlay_canvas' then overlay_canvas=value end
                if name=='Renderer' then renderer=value end
            end
            local function slot()
                return {IsValid=function()return true end,
                    SetAnchors=function(self,v)self.anchors=v end,
                    SetAlignment=function()end,SetAutoSize=function()end,
                    SetPosition=function(self,v)self.position=v end,
                    SetSize=function(self,v)self.size=v end}
            end
            local function canvas(name)
                return {IsValid=function()return true end,GetAddress=function()return name end,
                    GetFullName=function()return name end,SetVisibility=function()end,
                    SetRenderTransformPivot=function()end,SetRenderScale=function(self,v)self.scale=v end,
                    AddChildToCanvas=function()return slot() end}
            end
            function FName(name)return name end
            function StaticConstructObject(_,_,name)return canvas(name) end
            local host,outer,content,inner=overlay_canvas(canvas('Native'),nil,canvas('CanvasClass'))
            local g={position={X=140,Y=12},size={X=42,Y=24},scale={X=1,Y=1}}
            local r=setmetatable({host=host,slot=outer,canvas=content,content_slot=inner,
                options={pad_overlay=true,geometry=function()return g end}},renderer)
            for _,scale in ipairs({1,0.65,2}) do
                g.scale={X=scale,Y=scale}
                r:_sync_slot()
                -- Slate ignores offsets on stretched axes when computing a
                -- CanvasPanel's desired size. Fixed-axis children contribute.
                local width=outer.anchors.Minimum.X==outer.anchors.Maximum.X and
                    math.abs(outer.position.X)+outer.size.X or 0
                local height=outer.anchors.Minimum.Y==outer.anchors.Maximum.Y and
                    math.abs(outer.position.Y)+outer.size.Y or 0
                assert(width==0 and height==0)
                assert(inner.position.X==140-32*scale and inner.position.Y==12-32*scale)
                assert(inner.size.X==106 and inner.size.Y==56 and content.scale.X==scale)
            end
        ''')


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("package.path = ... .. '/?.lua;' .. package.path", SCRIPTS.as_posix())
        self.lua.execute('''
            function StaticFindObject() return {IsValid=function() return true end,GetAddress=function() return 99 end} end
            function widget(id) return {IsValid=function() return true end,GetAddress=function() return id end} end
            source,parent=widget(1),widget(2)
            bridge={geometry=function(id)
                if id==1 then return 200,40,1,120,240,0,0,1,0,0,1,120,240 end
                return 1920,1080,2,100,200,0,0,2,0,0,2,100,200
            end}
            geometry=require('ui_geometry').new(bridge)
        ''')

    def test_parent_dpi_scale_is_removed_from_local_coordinates(self):
        result = self.lua.eval('geometry:relative(source,parent)')
        self.assertEqual(result['position']['X'], 10)
        self.assertEqual(result['position']['Y'], 20)
        self.assertEqual(result['scale']['X'], 0.5)
        self.assertEqual(result['size']['X'], 200)

    def test_zero_geometry_is_retried_next_frame(self):
        self.lua.execute('bridge.geometry=function() return 0,0 end')
        self.assertIsNone(self.lua.eval('geometry:relative(source,parent)'))


if __name__ == '__main__':
    unittest.main()
