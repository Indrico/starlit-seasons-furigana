-- UE4SS adapter for the pure ruby_layout module. Call from the game thread only.
-- This adapter deliberately requires an existing CanvasPanel ancestor. It does
-- not reparent game widgets or alter the original dialogue/selection logic.
local Layout = require('ruby_layout')
local M = {}
local Renderer = {}
Renderer.__index = Renderer
local generated = {}

local function valid(object)
    return object and object:IsValid()
end

local function required(path)
    local object = StaticFindObject(path)
    assert(valid(object), 'Required Unreal object is unavailable: ' .. path)
    return object
end

local function create(class, outer)
    local object = StaticConstructObject(class, outer)
    assert(valid(object), 'Could not construct ' .. class:GetFullName())
    generated[object:GetAddress()] = object:GetFullName()
    return object
end

function M.is_generated(object)
    return valid(object) and generated[object:GetAddress()] == object:GetFullName()
end

function M.attach(source, options)
    options = options or {}
    assert(valid(source), 'A valid source text widget is required')
    local canvas_class = required('/Script/UMG.CanvasPanel')
    local parent = source:GetParent()
    while valid(parent) and not parent:IsA(canvas_class) do parent = parent:GetParent() end
    assert(valid(parent), 'The source text has no CanvasPanel ancestor')
    local text_slot = source.Slot
    local anchor_source = source
    local vertical_box_slot
    if valid(text_slot) and text_slot:IsA('/Script/UMG.VerticalBoxSlot') then
        local box = source:GetParent()
        assert(box:GetChildrenCount() == 1 and box:GetChildAt(0):GetAddress() == source:GetAddress(),
            'Only a single-text VerticalBox can host choice ruby')
        anchor_source, vertical_box_slot = box, text_slot
    end
    local source_slot = anchor_source.Slot
    assert(valid(source_slot) and source_slot:IsA('/Script/UMG.CanvasPanelSlot'),
        'The source text or its single-child VerticalBox must occupy a CanvasPanelSlot')
    local self = setmetatable({
        source = source, source_slot = source_slot, anchor_source = anchor_source,
        vertical_box_slot = vertical_box_slot, parent = parent, outer = source:GetOuter(),
        options = options, widgets = {}, widths = {}, heights = {}, previous_text = nil,
        text_class = required('/Script/UMG.TextBlock'),
        text_library = required('/Script/Engine.Default__KismetTextLibrary'),
        original_opacity = source.RenderOpacity,
    }, Renderer)
    self.font = options.font
    self.color = options.color
    local table_backed_style = false
    if not self.font then
        if source:IsA(self.text_class) then
            self.font, self.color = source.Font, source.ColorAndOpacity
        else
            local style = source.DefaultTextStyleOverride
            self.font, self.color = style.Font, style.ColorAndOpacity
            table_backed_style = not source.bOverrideDefaultStyle
        end
    end
    self.font_size = tonumber(self.font.Size)
    if (table_backed_style or not self.font_size or self.font_size <= 0 or not valid(self.font.FontObject)) and options.fallback_style then
        local fallback = options.fallback_style
        local holder = create(self.text_class, self.outer)
        local font = holder.Font
        local font_object = LoadAsset(fallback.font_asset or '/Game/Widget/Font/FONT-JP.FONT-JP')
        assert(valid(font_object), 'Could not load the original Japanese font')
        font.FontObject = font_object
        font.TypefaceFontName = FName(fallback.face or 'Text')
        font.Size = fallback.size or 29
        font.OutlineSettings.OutlineSize = fallback.outline_size or 0
        if fallback.outline_color then
            local color = font.OutlineSettings.OutlineColor
            color.R, color.G, color.B, color.A = table.unpack(fallback.outline_color)
        end
        holder:SetFont(font)
        self.font, self.font_size = holder.Font, tonumber(holder.Font.Size)
        if fallback.color then
            local color = holder.ColorAndOpacity.SpecifiedColor
            color.R, color.G, color.B, color.A = table.unpack(fallback.color)
            self.color = holder.ColorAndOpacity
        end
        self.font_holder = holder
    end
    assert(self.font_size and self.font_size > 0, 'The source font must be resolved before attaching ruby')
    -- The fallback font holder is also used for measurement, so its live font
    -- struct can change. Preserve the base outline before measuring any ruby.
    self.base_outline = tonumber(self.font.OutlineSettings.OutlineSize) or 0
    self.host = create(canvas_class, self.outer)
    self.host:SetVisibility(3) -- HitTestInvisible: preserve choice buttons below.
    self.slot = parent:AddChildToCanvas(self.host)
    assert(valid(self.slot), 'Could not attach ruby CanvasPanel')
    if vertical_box_slot then
        -- The outer canvas mirrors the font plate; the inner canvas mirrors the
        -- text's padding and render transform inside that one-child VerticalBox.
        self.canvas = create(canvas_class, self.outer)
        self.content_slot = self.host:AddChildToCanvas(self.canvas)
        self.canvas:SetVisibility(3)
    else
        self.canvas = self.host
    end
    self.canvas:SetClipping(1) -- ClipToBounds; font fitting keeps visible runs inside.
    self:_sync_slot()
    self.slot:SetZOrder(options.z_order or 1000)
    if self.font_holder then
        self.measure_widget = self.font_holder
        self.canvas:AddChildToCanvas(self.measure_widget):SetAutoSize(true)
    else
        self.measure_widget = self:_text_widget()
    end
    self.measure_widget:SetRenderOpacity(0)
    self.measure_widget:SetVisibility(1)
    return self
end

function Renderer:_text_widget()
    local block = create(self.text_class, self.outer)
    block:SetFont(self.font)
    if self.color then block:SetColorAndOpacity(self.color) end
    block:SetVisibility(3)
    local slot = self.canvas:AddChildToCanvas(block)
    slot:SetAutoSize(true)
    return block, slot
end

function Renderer:_set_text(block, text, size, role)
    -- SetFont copies the source font. Changes to the child's font do not modify
    -- the original dialogue widget's FSlateFontInfo.
    block:SetFont(self.font)
    local font = block.Font
    font.Size = size
    font.OutlineSettings.OutlineSize = role == 'ruby' and 0 or self.base_outline
    block:SetFont(font)
    block:SetText(self.text_library:Conv_StringToText(text))
end

function Renderer:_measure(text, size, role)
    role = role or 'base'
    local font_key = role .. ':' .. tostring(size)
    local key = font_key .. ':' .. text
    if not self.widths[key] then
        self.measure_widget:SetVisibility(3)
        self:_set_text(self.measure_widget, text, size, role)
        self.measure_widget:InvalidateLayoutAndVolatility()
        self.measure_widget:ForceLayoutPrepass()
        self.canvas:ForceLayoutPrepass()
        local size_box = self.measure_widget:GetDesiredSize()
        self.measure_widget:SetVisibility(1)
        self.widths[key] = size_box.X
        self.heights[font_key] = math.max(self.heights[font_key] or 0, size_box.Y)
    end
    return self.widths[key]
end

function Renderer:_anchor_size()
    local size = self.source_slot:GetSize()
    if self.source_slot.bAutoSize then size = self.anchor_source:GetDesiredSize() end
    return size
end

function Renderer:_padding()
    if not self.vertical_box_slot then return {Left = 0, Top = 0, Right = 0, Bottom = 0} end
    return self.vertical_box_slot.Padding
end

function Renderer:_size()
    local size, padding = self:_anchor_size(), self:_padding()
    return {X = size.X - padding.Left - padding.Right, Y = size.Y - padding.Top - padding.Bottom}
end

function Renderer:_sync_slot()
    -- FGeometry is opaque and marshals as zeroes on this game's UE4SS build.
    -- A sibling CanvasPanelSlot can share the source's reflected layout exactly.
    self.slot:SetAnchors(self.source_slot:GetAnchors())
    self.slot:SetAlignment(self.source_slot:GetAlignment())
    self.slot:SetPosition(self.source_slot:GetPosition())
    self.slot:SetSize(self:_anchor_size())
    self.slot:SetAutoSize(false)
    self.host:SetRenderTransform(self.anchor_source.RenderTransform)
    self.host:SetRenderTransformPivot(self.anchor_source.RenderTransformPivot)
    if self.content_slot then
        local padding = self:_padding()
        self.content_slot:SetPosition({X = padding.Left, Y = padding.Top})
        self.content_slot:SetSize(self:_size())
        self.content_slot:SetAutoSize(false)
        self.canvas:SetRenderTransform(self.source.RenderTransform)
        self.canvas:SetRenderTransformPivot(self.source.RenderTransformPivot)
    end
end

function Renderer:_pooled(index)
    if not self.widgets[index] then
        local base, base_slot = self:_text_widget()
        local ruby, ruby_slot = self:_text_widget()
        self.widgets[index] = {base = base, base_slot = base_slot, ruby = ruby, ruby_slot = ruby_slot}
    end
    return self.widgets[index]
end

function Renderer:_source_visible()
    local widget = self.source
    while valid(widget) do
        if not widget:IsVisible() then return false end
        if widget:GetAddress() == self.parent:GetAddress() then break end
        widget = widget:GetParent()
    end
    return true
end

function Renderer:geometry_key()
    if not valid(self.source) or not valid(self.parent) then return nil end
    local layout = self.source_slot.LayoutData
    local o, a, n, x = layout.Offsets, layout.Alignment, layout.Anchors.Minimum, layout.Anchors.Maximum
    local t = self.source.RenderTransform
    local padding = self:_padding()
    local size = self:_size()
    return string.format('%.2f:%.2f:%.2f:%.2f:%.2f:%.2f:%.3f:%.3f:%.3f:%.3f:%.2f:%.2f:%.3f:%.3f:%.3f:%.2f:%.2f:%.2f:%.2f:%s',
        o.Left, o.Top, size.X, size.Y, a.X, a.Y, n.X, n.Y, x.X, x.Y,
        t.Translation.X, t.Translation.Y, t.Scale.X, t.Scale.Y, t.Angle,
        padding.Left, padding.Top, padding.Right, padding.Bottom, tostring(self:_source_visible()))
end

function Renderer:hide()
    if valid(self.host) then self.host:SetVisibility(1) end
    if valid(self.source) then self.source:SetRenderOpacity(self.original_opacity) end
    self.previous_text = nil
end

function Renderer:detach()
    self:hide()
    if valid(self.host) then self.host:RemoveFromParent() end
end

function Renderer:update(segments, visible_count)
    if not valid(self.source) or not valid(self.parent) then return false, 'Source widget expired' end
    if not self:_source_visible() then self:hide(); return false, 'Source widget or its ancestor is hidden' end
    local source_text = Layout.text(segments)
    if source_text:find('<[^>]+>') then
        self:hide()
        return false, 'Rich-text markup requires a style-preserving parser'
    end
    local size = self:_size()
    if size.X <= 0 or size.Y <= 0 then
        self:hide(); return false, 'Source geometry is not ready'
    end
    self:_sync_slot()
    -- Hidden canvases may retain stale desired sizes. Measure while visible but
    -- fully transparent; swap to generated text only after a successful layout.
    self.host:SetVisibility(3)
    self.host:SetRenderOpacity(0)
    local margin = self.source.Margin
    local width = self.options.width or math.max(1, size.X - margin.Left - margin.Right)
    local original_height = math.max(1, size.Y - margin.Top - margin.Bottom)
    local slack = math.max(0, self.options.max_vertical_slack or 0)
    local height = original_height + slack
    local minimum = math.min(self.font_size, self.options.min_base_size or 18)
    local result
    for base_size = self.font_size, minimum, -1 do
        local ruby_size = math.max(8, math.floor(base_size * (self.options.ruby_scale or 0.48)))
        self:_measure('国', base_size, 'base')
        self:_measure('あ', ruby_size, 'ruby')
        local base_height = self.options.base_height or self.heights['base:' .. tostring(base_size)]
        local ruby_height = self.options.ruby_height or self.heights['ruby:' .. tostring(ruby_size)]
        result = Layout.layout(segments, {
            width = width,
            measure = function(text, font_size, role) return self:_measure(text, font_size, role) end,
            base_size = base_size,
            ruby_size = ruby_size,
            visible_count = visible_count,
            base_height = base_height,
            ruby_height = ruby_height,
            gap = self.options.gap,
            line_gap = self.options.line_gap,
            justification = tonumber(self.source.Justification),
        })
        result.fit_summary = string.format('base=%d ruby=%d lines=%d height=%.2f/%.2f baseH=%.2f rubyH=%.2f width=%.2f',
            base_size, ruby_size, result.lines, result.height, height, base_height, ruby_height, width)
        if result.height <= height then break end
    end
    if not result or result.height > height then
        self:hide(); return false, 'Ruby does not fit the source rectangle at the minimum readable font size; ' ..
            (result and result.fit_summary or 'no layout result')
    end
    local added_height = math.max(0, math.ceil(result.height - original_height))
    if added_height > 0 then
        local alignment = self.source_slot:GetAlignment()
        local position = self.source_slot:GetPosition()
        self.slot:SetSize({X = size.X, Y = size.Y + added_height})
        self.slot:SetPosition({X = position.X, Y = position.Y + added_height * alignment.Y})
    end
    result.fit_summary = result.fit_summary .. string.format(' canvasH=%.2f slack=%d', size.Y + added_height, added_height)
    local vertical_offset = 0
    if self.vertical_box_slot then
        local alignment = tonumber(self.vertical_box_slot.VerticalAlignment)
        if alignment == 2 then vertical_offset = math.max(0, original_height - result.height) / 2 end
        if alignment == 3 then vertical_offset = math.max(0, original_height - result.height) end
    end
    for index, run in ipairs(result.runs) do
        local pair = self:_pooled(index)
        local base_size = run.base_size
        local ruby_size_scaled = run.ruby_size
        if pair.base_text ~= run.base or pair.base_size ~= base_size then
            self:_set_text(pair.base, run.base, base_size, 'base')
            pair.base_text, pair.base_size = run.base, base_size
        end
        local base_x, base_y = margin.Left + run.x, margin.Top + vertical_offset + run.y
        if pair.base_x ~= base_x or pair.base_y ~= base_y then
            pair.base_slot:SetPosition({X = base_x, Y = base_y})
            pair.base_x, pair.base_y = base_x, base_y
        end
        pair.base:SetVisibility(3)
        if run.reading then
            if pair.ruby_text ~= run.reading or pair.ruby_size ~= ruby_size_scaled then
                self:_set_text(pair.ruby, run.reading, ruby_size_scaled, 'ruby')
                pair.ruby_text, pair.ruby_size = run.reading, ruby_size_scaled
            end
            local ruby_x, ruby_y = margin.Left + run.ruby_x, margin.Top + vertical_offset + run.ruby_y
            if pair.ruby_x ~= ruby_x or pair.ruby_y ~= ruby_y then
                pair.ruby_slot:SetPosition({X = ruby_x, Y = ruby_y})
                pair.ruby_x, pair.ruby_y = ruby_x, ruby_y
            end
            pair.ruby:SetVisibility(3)
        else
            pair.ruby:SetVisibility(1)
        end
    end
    for index = #result.runs + 1, #self.widgets do
        self.widgets[index].base:SetVisibility(1)
        self.widgets[index].ruby:SetVisibility(1)
    end
    self.host:SetVisibility(3)
    self.host:SetRenderOpacity(1)
    self.source:SetRenderOpacity(0)
    self.previous_text = source_text
    return true, result
end

return M
