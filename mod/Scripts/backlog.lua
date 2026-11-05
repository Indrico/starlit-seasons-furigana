-- Grow native log cards together; their native order, focus and voice IDs stay.
local M = {}
local function valid(w) return w and w:IsValid() end
local function canvas_slot(w)
    return valid(w) and valid(w.Slot) and w.Slot:IsA('/Script/UMG.CanvasPanelSlot') and w.Slot or nil
end

function M.new()
    local self = {nodes = {}, scrolls = {}, frame = 0, revision = 0}
    function self:begin_frame()
        self.frame = self.frame + 1
        for _, box in pairs(self.scrolls) do
            if box.pin and self.frame >= box.pin.frame then
                local scroll, offset = box.owner, box.pin.offset
                box.pin = nil
                if valid(scroll) and scroll:GetFullName() == box.name and scroll:IsVisible() and
                    scroll:GetScrollOffset() >= offset - 1 then
                    scroll:ScrollToEnd()
                end
            end
        end
    end
    function self:describe(source)
        local node = source:GetOuter()
        for _ = 1, 6 do
            if not valid(node) then return nil end
            if node:IsA('/Script/imal.WidgetCommuScriptLogNode') then break end
            node = node:GetOuter()
        end
        if not valid(node) or not node:IsA('/Script/imal.WidgetCommuScriptLogNode') then return nil end
        local message, mini
        for _, field in ipairs({'_TextSelectMessage','_TextNonSelectMessage','_TextSelectRanko','_TextNonSelectRanko',
                                '_TextSelectMini','_TextNonSelectMini'}) do
            local w = node[field]
            if valid(w) and w:GetAddress() == source:GetAddress() then
                message, mini = true, field:find('Mini',1,true) ~= nil
                break
            end
        end
        return {node = node, message = message, mini = mini}
    end
    function self:state(node)
        local address, name = node:GetAddress(), node:GetFullName()
        local state = self.nodes[address]
        if state and state.name == name then return state end
        state = {node = node, name = name, slots = {}, heights = {}, source_slots = {}}
        function state:save(slot)
            if not valid(slot) then return nil end
            local address = slot:GetAddress()
            if not self.slots[address] then
                local p, s = slot:GetPosition(), slot:GetSize()
                self.slots[address] = {slot = slot, name = slot:GetFullName(), x = p.X, y = p.Y, width = s.X, height = s.Y}
            end
            return self.slots[address]
        end
        function state:restore()
            for _, saved in pairs(self.slots) do
                if valid(saved.slot) and saved.slot:GetFullName() == saved.name then
                    saved.slot:SetPosition({X = saved.x, Y = saved.y})
                    saved.slot:SetSize({X = saved.width, Y = saved.height})
                end
            end
        end
        self.nodes[address] = state
        return state
    end
    function self:in_range(description, geometry)
        local node, scroll = description.node, description.node:GetParent()
        for _ = 1, 6 do
            if not valid(scroll) then return false end
            if scroll:IsA('/Script/UMG.ScrollBox') then break end
            scroll = scroll:GetParent()
        end
        if not valid(scroll) or not scroll:IsA('/Script/UMG.ScrollBox') then return false end
        description.scroll = scroll
        local address, name = scroll:GetAddress(), scroll:GetFullName()
        local box = self.scrolls[address]
        if not box or box.name ~= name then box = {owner = scroll, name = name}; self.scrolls[address] = box end
        if box.frame ~= self.frame then
            box.frame = self.frame
            box.offset = scroll:GetScrollOffset()
            box.at_end = box.offset >= scroll:GetScrollOffsetOfEnd() - 1
            local count = scroll:GetChildrenCount()
            if box.revision ~= self.revision or box.count ~= count then
                box.revision, box.count, box.cursor, box.top, box.rows = self.revision, count, 0, 0, {}
            end
            -- Offscreen widgets retain their last painted cached geometry.
            -- Derive positions from native desired heights and scroll offset,
            -- admitting at most eight rows per frame when rebuilding the map.
            for _ = 1, 8 do
                if box.cursor >= count then break end
                local child = scroll:GetChildAt(box.cursor)
                if valid(child) and tonumber(child:GetVisibility()) ~= 1 then
                    local height = child:GetDesiredSize().Y
                    local padding = child.Slot.Padding
                    local top, bottom = padding.Top, padding.Bottom
                    box.rows[child:GetAddress()] = {top = box.top + top, height = height}
                    box.top = box.top + top + height + bottom
                end
                box.cursor = box.cursor + 1
            end
        end
        -- Keep existing overlays during a bounded rebuild; admit new ones
        -- only once the complete native row order is available.
        if box.cursor < box.count then return nil end
        local row, viewport = box.rows[node:GetAddress()], geometry:read(scroll)
        if not row or not viewport then return false end
        local height, y = row.height, row.top - box.offset
        -- Visible cards plus one card above/below the clipping rectangle.
        return y + height >= -height and y <= viewport[2] + height
    end
    function self:grow(description, height)
        local node = description.node
        if not valid(node) then return end
        local state = self:state(node)
        local family = description.mini and 'Mini' or 'Default'
        local target = math.ceil(height)
        if state.heights[family] and state.heights[family] >= target then return end
        state.heights[family] = math.max(state.heights[family] or 0, target)
        self.revision = self.revision + 1
        local top = 16
        local text_fields = description.mini and {'_TextSelectMini','_TextNonSelectMini'} or
            {'_TextSelectMessage','_TextNonSelectMessage','_TextSelectRanko','_TextNonSelectRanko'}
        local extra = top
        for _, field in ipairs(text_fields) do
            local slot = canvas_slot(node[field])
            if slot then
                local saved = state:save(slot)
                local h = math.max(saved.height, target)
                slot:SetPosition({X = saved.x, Y = saved.y + top})
                slot:SetSize({X = saved.width, Y = h})
                extra = math.max(extra, top + h - saved.height)
            end
        end
        if not description.mini then
            for _, field in ipairs({'_TextSelectName','_TextNonSelectName'}) do
                local slot = canvas_slot(node[field])
                if slot then local saved = state:save(slot); slot:SetPosition({X = saved.x, Y = saved.y + top}) end
            end
        end
        state.extra = math.max(state.extra or 0, extra)
        for _, field in ipairs({'_PanelSelectDefault', '_PanelNonSelectDefault', '_PanelSelectMini', '_PanelNonSelectMini'}) do
            local panel = node[field]
            -- Both families are GridPanel children. Their CanvasPanel parent
            -- slot controls the ScrollBox row's desired height. The plates and
            -- voice controls already stretch/anchor to that height; changing
            -- their offsets would shrink a plate or move its icon twice.
            local container = valid(panel) and panel:GetParent() or nil
            local slot = canvas_slot(container) or canvas_slot(panel)
            if slot then
                local saved = state:save(slot)
                slot:SetSize({X = saved.width, Y = saved.height + state.extra})
            end
        end
        node:InvalidateLayoutAndVolatility()
        local scroll = description.scroll
        local box = valid(scroll) and self.scrolls[scroll:GetAddress()] or nil
        -- Native opening/navigation may already be at the last card. Keep
        -- that endpoint visible after height changes without pulling a user
        -- who has scrolled upward back to the bottom.
        -- Give Slate a layout pass before resolving the new end offset.
        if box and box.at_end then box.pin = {frame = self.frame + 2, offset = box.offset} end
    end
    function self:release(node)
        if not valid(node) then return end
        local state = self.nodes[node:GetAddress()]
        if state then state:restore(); self.nodes[node:GetAddress()] = nil; self.revision = self.revision + 1 end
    end
    function self:clear()
        for _, state in pairs(self.nodes) do state:restore() end
        self.nodes, self.scrolls = {}, {}
        self.revision = self.revision + 1
    end
    function self:prune()
        for address, state in pairs(self.nodes) do
            if not valid(state.node) or state.node:GetFullName() ~= state.name then self.nodes[address] = nil end
        end
        for address, box in pairs(self.scrolls) do
            if not valid(box.owner) or box.owner:GetFullName() ~= box.name then self.scrolls[address] = nil end
        end
    end
    return self
end
return M
