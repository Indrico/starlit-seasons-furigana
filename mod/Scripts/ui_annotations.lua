-- Menu/name/backlog annotations have their own lifecycle: never advance lines.
local Registry = require('object_registry')
local Ruby = require('umg_ruby')
local Lookup = require('reading_lookup')
local Sha = require('sha256')
local M = {}
local DEFERRED = {}

local function valid(w) return w and w:IsValid() end

function M.eligible(w)
    if Ruby.is_generated(w) then return false end
    local name = w:GetFullName()
    if not name:find('/Engine/Transient.', 1, true) or not name:find('WBP_', 1, true) then return false end
    if name:find('WBP_Commu_MessageName', 1, true) then return true end
    if name:find('WBP_Commu_Message_C', 1, true) or name:find('WBP_Commu_Cinema_C', 1, true) or
        name:find('WBP_Commu_Text_C', 1, true) or name:find('WBP_Commu_NovelText_C', 1, true) or
        name:find('WBP_Commu_Select_C', 1, true) or name:lower():find('lyric', 1, true) then return false end
    return true
end

local function visible(w, renderer)
    local first, top = true, nil
    while valid(w) do
        if not w:IsVisible() then return false end
        if w:IsA('/Script/UMG.UserWidget') then top = w end
        if w.RenderOpacity and w.RenderOpacity < 0.01 and not (first and renderer and not renderer.options.overlay_only) then return false end
        first, w = false, Ruby.parent_of(w)
    end
    return not top or top:IsInViewport()
end

function M.new(database, bridge, image_bindings, log)
    local self = {entries = {}, order = {}, listed = {}, urgent = {}, groups = {}, active = {}, cursor = 1, enabled = true,
        geometry = require('ui_geometry').new(bridge), bindings = image_bindings or {},
        backlog = require('backlog').new(),
        lookup = {}, lookup_keys = {}, lookup_cursor = 1}
    local now = function() return bridge and bridge.clock and bridge.clock() or os.clock() end
    local function candidate(w)
        if not M.eligible(w) then return false end
        if not w:IsA('/Script/UMG.Image') then return true end
        local name = w:GetFName():ToString():lower()
        if name:find('name', 1, true) or name:find('text', 1, true) or name:find('title', 1, true) then return true end
        local resource = w.Brush.ResourceObject
        if not valid(resource) then return false end
        local asset = resource:GetFName():ToString():lower()
        return asset:find('wdt_name_',1,true) or asset:find('wdt_dlc_name_',1,true) or
            asset:find('name_jp_',1,true) or (self.bindings.images or {})[Sha.hex(asset)] ~= nil
    end
    self.registry = Registry.new({'/Script/UMG.TextBlock', '/Script/UMG.RichTextBlock'}, candidate,
        {incremental = true, admit_limit = 8})
    self.images = Registry.new({'/Script/UMG.Image'}, candidate, {incremental = true, admit_limit = 8})
    function self:group_for(w)
        local root, parent = nil, w
        for _ = 1, 48 do
            if not valid(parent) then break end
            if parent:IsA('/Script/UMG.UserWidget') then root = parent end
            parent = Ruby.parent_of(parent)
        end
        if not root then return nil end
        local address, name = root:GetAddress(), root:GetFullName()
        local group = self.groups[address]
        if not group or group.name ~= name then
            group = {owner = root, name = name, active = false}
            self.groups[address] = group
        end
        return group
    end
    function self:set_enabled(value)
        self.enabled = value
        for _, entry in pairs(self.entries) do entry.next_poll = 0 end
        if not value then
            self.urgent = {}
            self.work = nil
            self.active = {}
            self.backlog:clear()
            for _, entry in pairs(self.entries) do
                if entry.renderer then entry.renderer:detach() end
            end
            for _, entry in pairs(self.entries) do entry.renderer, entry.key, entry.pending_key = nil, nil, nil end
        end
    end
    function self:segments(text)
        local cached = self.lookup[text]
        if cached ~= nil then return cached or nil end
        local result = Lookup.get(database, text)
        local old = self.lookup_keys[self.lookup_cursor]
        if old then self.lookup[old] = nil end
        self.lookup_keys[self.lookup_cursor] = text
        self.lookup_cursor = self.lookup_cursor % 2048 + 1
        self.lookup[text] = result or false
        return result
    end
    function self:inspect(entry, deadline)
        self.deadline = deadline
        local w = entry.source
        if entry.backlog == nil and not w:IsA('/Script/UMG.Image') then entry.backlog = self.backlog:describe(w) or false end
        local in_range = entry.backlog and self.backlog:in_range(entry.backlog, self.geometry)
        if entry.backlog and in_range == nil then return end
        if entry.backlog and not in_range then
            if entry.renderer then entry.renderer:detach(); entry.renderer = nil end
            entry.key, entry.pending_key = nil, nil
            return
        end
        if not visible(w, entry.renderer) then
            if entry.renderer then entry.renderer:detach(); entry.renderer = nil end
            entry.pending_key = nil
            entry.key = nil; return
        end
        if w:IsA('/Script/UMG.Image') then
            local resource = w.Brush.ResourceObject
            if not valid(resource) then return end
            local identity = resource:GetFName():ToString():lower()
            if identity ~= entry.image then
                if entry.renderer then entry.renderer:detach(); entry.renderer = nil end
                entry.image = identity
                entry.binding = (self.bindings.images or {})[Sha.hex(identity)]
            end
            if not entry.binding then return end
            if not entry.renderer then
                entry.renderer = Ruby.attach_image(w, function(source, parent) return self.geometry:relative(source, parent) end)
                self.active[w:GetAddress()] = entry
            end
            entry.renderer:update(entry.binding)
            return
        end
        local text = w:GetText():ToString()
        if entry.text and entry.text ~= text and entry.renderer then
            entry.renderer:hide(); entry.key, entry.pending_key = nil, nil
        end
        local short = w:GetFName():ToString():lower()
        if not w:IsA('/Script/UMG.TextBlock') and not w.bOverrideDefaultStyle then
            -- A table-backed rich style has no reflected resolved font. Never
            -- guess its native metrics when placing a ruby-only overlay.
            return
        end
        local person_name = entry.name:find('WBP_Commu_MessageName', 1, true) or
            entry.name:find('Idol_name', 1, true) or (entry.name:find('WBP_Commu_LogNode_C', 1, true) and short:find('name', 1, true))
        if person_name and not (self.bindings.names or {})[Sha.hex(text)] then return end
        if w:IsA('/Script/UMG.TextBlock') then
            local f, c = w.Font, w.ColorAndOpacity.SpecifiedColor
            local style = string.format('%s:%s:%s:%s:%s:%s', f.Size, f.OutlineSettings.OutlineSize, c.R, c.G, c.B, c.A)
            if entry.style and entry.style ~= style and entry.renderer then
                entry.renderer:detach(); entry.renderer, entry.key, entry.pending_key = nil, nil, nil
            end
            entry.style = style
        end
        if text ~= entry.text then
            if entry.renderer then entry.renderer:hide() end
            entry.text, entry.segments, entry.key = text, self:segments(text), nil
        end
        if not entry.segments or text:find('<[^>]+>') then return end
        if not entry.renderer then
            local parent = Ruby.parent_of(w)
            while valid(parent) and not parent:IsA('/Script/UMG.CanvasPanel') do parent = Ruby.parent_of(parent) end
            if not valid(parent) or not self.geometry:relative(w, parent) then return end
            local backlog = entry.backlog
            local menu_min = w:IsA('/Script/UMG.TextBlock') and math.max(7, math.min(11, math.floor(w.Font.Size*0.6))) or 11
            entry.renderer = Ruby.attach(w, {fixed_size = true, min_ruby_size = (backlog or person_name) and 14 or menu_min,
                ruby_scale = (backlog or person_name) and 0.5 or 0.4,
                overlay_only = not (backlog and backlog.message), gap = -12, line_gap = 4,
                pad_overlay = not backlog, ruby_outline = 1,
                -- UE4SS binds reflected calls to its registered Lua state;
                -- coroutines have an unregistered state. Stop after a cached
                -- measurement/run and restart from that cache next tick.
                yield_work = function()
                    if self.deadline and now() >= self.deadline then error(DEFERRED, 0) end
                end,
                grow = backlog and backlog.message and function(height) self.backlog:grow(backlog, height) end or nil,
                geometry = function(source, host) return self.geometry:relative(source, host) end,
                fallback_style = {font_asset = '/Game/Widget/Font/FONT-JP.FONT-JP', face = 'Text', size = 29,
                    color = {0.033105, 0.033105, 0.033105, 1}},
            })
            self.active[w:GetAddress()] = entry
        end
        local geometry = entry.renderer:geometry_key()
        if not geometry then entry.renderer:hide(); entry.key = nil; return end
        local key = text .. '\0' .. geometry
        if key ~= entry.key then
            if entry.pending_key ~= key then
                entry.renderer:hide()
                entry.pending_key = key
            end
            local resumed, applied, reason = pcall(entry.renderer.update, entry.renderer, entry.segments, utf8.len(text))
            if not resumed then
                if applied == DEFERRED then self.work = entry; return end
                error(applied)
            end
            entry.pending_key = nil
            if self.work == entry then self.work = nil end
            entry.key = applied and key or nil
            if applied then entry.applied = true end
            if not applied and not entry.refused then
                log('UI annotation kept native layout (' .. tostring(reason) .. '): ' .. entry.name)
                entry.refused = true
            end
        end
    end
    function self:changed(w)
        if not self.enabled or not valid(w) or not M.eligible(w) then return end
        local address, name = w:GetAddress(), w:GetFullName()
        local entry = self.entries[address]
        if entry and entry.name == name then
            if entry.renderer then entry.renderer:hide() end
            entry.key, entry.pending_key = nil, nil
            entry.next_poll = 0
        else
            if entry and entry.renderer then entry.renderer:detach() end
            entry = {source = w, name = name, group = self:group_for(w)}
            self.entries[address] = entry
            if not self.listed[address] then self.order[#self.order+1] = address;self.listed[address] = true end
        end
        self.urgent[address] = entry
    end
    function self:tick()
        local started = now()
        self.geometry:begin_frame()
        self.backlog:begin_frame()
        self.backlog:prune()
        local incoming = self.registry:take_new()
        for _, w in ipairs(self.images:take_new()) do incoming[#incoming+1] = w end
        for _, w in ipairs(incoming) do
            local address = w:GetAddress()
            local entry = self.entries[address]
            local name = w:GetFullName()
            if not entry or entry.name ~= name then
                if entry and entry.renderer then entry.renderer:detach() end
                self.entries[address] = {source = w, name = name, group = self:group_for(w)}
                if not self.listed[address] then self.order[#self.order+1] = address;self.listed[address] = true end
            end
        end
        if not self.enabled then return end
        local count = #self.order
        for address, group in pairs(self.groups) do
            if started < (group.next_check or 0) then
                -- Root visibility is shared by every label on that screen.
            elseif not valid(group.owner) or group.owner:GetFullName() ~= group.name then
                group.active, group.expired = false, true
                self.groups[address] = nil
            else
                group.active = group.owner:IsInViewport() and group.owner:IsVisible() and group.owner.RenderOpacity >= 0.01
                group.next_check = started + 0.1
            end
            if now() - started >= 0.002 then return end
        end
        -- Rotate existing overlays within half the budget, leaving time for
        -- newly visible sources. Identity checks also wait for the poll time;
        -- checking every inactive overlay on every tick starves discovery.
        local active_order = {}
        for address in pairs(self.active) do active_order[#active_order+1] = address end
        for _ = 1, #active_order do
            self.active_cursor = (self.active_cursor or 0) % #active_order + 1
            local address = active_order[self.active_cursor]
            local entry = self.active[address]
            if not entry.renderer then self.active[address] = nil
            elseif self.enabled and started >= (entry.next_poll or 0) then
                if not valid(entry.source) or entry.source:GetFullName() ~= entry.name then
                    entry.renderer:detach(); entry.renderer = nil; entry.pending_key = nil
                    self.active[address] = nil
                else
                    local ok, reason = pcall(self.inspect, self, entry, started + 0.001)
                    entry.next_poll = started + 0.05
                    if not ok then
                        if entry.renderer then entry.renderer:detach() end
                        entry.renderer = nil; entry.pending_key = nil
                        self.active[address] = nil
                        if not entry.reported then log('UI refresh retained native text: '..tostring(reason));entry.reported = true end
                    end
                end
            end
            if now() - started >= 0.001 then break end
        end
        for address, entry in pairs(self.urgent) do
            self.urgent[address] = nil
            if valid(entry.source) and entry.source:GetFullName() == entry.name then
                pcall(self.inspect, self, entry, started + 0.002)
            end
            if now() - started >= 0.002 then return end
        end
        if self.work then
            local entry = self.work
            self.work = nil
            if self.enabled and valid(entry.source) and entry.source:GetFullName() == entry.name then
                local ok, reason = pcall(self.inspect, self, entry, started + 0.002)
                if not ok then
                    if entry.renderer then entry.renderer:detach(); entry.renderer = nil end
                    entry.pending_key = nil
                    if not entry.reported then log('UI preparation retained native text: ' .. tostring(reason)); entry.reported = true end
                end
            end
            if now() - started >= 0.002 then return end
        end
        for index = 1, count do
            if self.cursor > #self.order then self.cursor = 1 end
            local address = self.order[self.cursor]
            if not address then break end
            local entry = self.entries[address]
            if entry and entry.group and not entry.group.active and not entry.group.expired then
                if entry.renderer then entry.renderer:detach(); entry.renderer = nil; entry.key = nil end
                entry.pending_key = nil
                if entry.backlog then self.backlog:release(entry.backlog.node); entry.backlog = nil end
                self.cursor = self.cursor + 1
            elseif entry and started < (entry.next_poll or 0) then
                self.cursor = self.cursor + 1
            elseif not entry or (entry.group and entry.group.expired) or not valid(entry.source) or entry.source:GetFullName() ~= entry.name then
                if entry and entry.renderer then entry.renderer:detach() end
                self.entries[address] = nil
                self.listed[address] = nil
                self.registry:forget(address)
                self.images:forget(address)
                table.remove(self.order, self.cursor)
            else
                local ok, reason = true, nil
                if self.enabled then ok, reason = pcall(self.inspect, self, entry, started + 0.002) end
                entry.next_poll = started + (entry.renderer and 0.05 or 0.25)
                if not ok then
                    if entry.renderer then entry.renderer:detach(); entry.renderer = nil end
                    entry.pending_key = nil
                    if not entry.reported then log('UI annotation retained native text: ' .. tostring(reason)); entry.reported = true end
                end
                self.cursor = self.cursor + 1
            end
            if index % 8 == 0 and now() - started >= 0.002 then break end
        end
    end
    function self:stats()
        local renderers, widgets, cached = 0, 0, 0
        for _, entry in pairs(self.entries) do
            if entry.renderer then
                renderers = renderers + 1
                widgets = widgets + #(entry.renderer.widgets or {})
            end
        end
        for _ in pairs(self.lookup) do cached = cached + 1 end
        return #self.order, renderers, widgets, cached, collectgarbage('count')
    end
    if RegisterHook then
        for _, class in ipairs({'TextBlock', 'RichTextBlock'}) do
            pcall(RegisterHook, '/Script/UMG.' .. class .. ':SetText', function() end, function(context)
                local ok, w = pcall(function() return context:get() end)
                if ok then pcall(self.changed, self, w) end
            end)
        end
    end
    return self
end
return M
