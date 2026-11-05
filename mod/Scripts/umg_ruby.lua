-- UE4SS adapter for the pure ruby_layout module. Call from the game thread only.
-- This adapter deliberately requires an existing CanvasPanel ancestor. It does
-- not reparent game widgets or alter the original dialogue/selection logic.
local Layout = require('ruby_layout')
local M = {}
local Renderer = {}
Renderer.__index = Renderer
-- Weak values do not retain expired scene widgets or an ever-growing name map.
local generated = setmetatable({}, {__mode = 'v'})
local generated_names = setmetatable({}, {__mode = 'k'})
local generated_sequence = 0

local function valid(object)
    return object and object:IsValid()
end

-- A widget-tree root has no Panel parent. Continue through its owning
-- UserWidget so nested reusable controls can share an outer CanvasPanel.
function M.parent_of(widget)
    local parent = widget:GetParent()
    if valid(parent) then return parent end
    local outer = widget:GetOuter()
    for _ = 1, 4 do
        if not valid(outer) then return nil end
        if outer:IsA('/Script/UMG.UserWidget') then return outer end
        outer = outer:GetOuter()
    end
end

function M.scroll_parent(widget)
    local parent = M.parent_of(widget)
    for _ = 1, 48 do
        if not valid(parent) then return nil end
        if parent:IsA('/Script/UMG.ScrollBox') then return parent end
        parent = M.parent_of(parent)
    end
end

local function required(path)
    local object = StaticFindObject(path)
    assert(valid(object), 'Required Unreal object is unavailable: ' .. path)
    return object
end

local function create(class, outer)
    generated_sequence = generated_sequence + 1
    local object = StaticConstructObject(class, outer, FName('StarlitFuriganaGenerated_' .. generated_sequence))
    assert(valid(object), 'Could not construct ' .. class:GetFullName())
    generated[object:GetAddress()] = object
    generated_names[object] = object:GetFullName()
    return object
end

function M.is_generated(object)
    if not valid(object) then return false end
    if object:GetFName():ToString():find('^StarlitFuriganaGenerated_') then return true end
    local made = generated[object:GetAddress()]
    return valid(made) and generated_names[made] == object:GetFullName()
end

function M.attach_image(source, geometry)
    local parent = M.parent_of(source)
    while valid(parent) and not parent:IsA('/Script/UMG.CanvasPanel') do parent = M.parent_of(parent) end
    assert(valid(parent), 'Image has no CanvasPanel ancestor')
    local outer = source:GetOuter()
    local host = create(required('/Script/UMG.CanvasPanel'), outer)
    local name = host:GetFullName()
    local slot = parent:AddChildToCanvas(host)
    slot:SetAnchors({Minimum = {X = 0, Y = 0}, Maximum = {X = 0, Y = 0}})
    slot:SetAlignment({X = 0, Y = 0})
    slot:SetAutoSize(false)
    slot:SetZOrder(1000)
    host:SetVisibility(3)
    host:SetClipping(M.scroll_parent(source) and 1 or 2)
    local label = create(required('/Script/UMG.TextBlock'), outer)
    local font = label.Font
    font.FontObject = LoadAsset('/Game/Widget/Font/FONT-JP.FONT-JP')
    font.TypefaceFontName = FName('Text')
    font.Size = 14
    font.OutlineSettings.OutlineSize = 1
    local outline = font.OutlineSettings.OutlineColor
    outline.R, outline.G, outline.B, outline.A = 1, 1, 1, 0.9
    label:SetFont(font)
    local color = label.ColorAndOpacity
    color.SpecifiedColor.R, color.SpecifiedColor.G, color.SpecifiedColor.B, color.SpecifiedColor.A = 0.03, 0.03, 0.03, 1
    label:SetColorAndOpacity(color)
    label:SetVisibility(3)
    local text_slot = host:AddChildToCanvas(label)
    text_slot:SetAutoSize(true)
    local result = {source = source, parent = parent, options = {overlay_only = true}}
    function result:hide() if valid(host) and host:GetFullName() == name then host:SetVisibility(1) end end
    function result:detach() self:hide(); if valid(host) and host:GetFullName() == name then host:RemoveFromParent() end end
    function result:update(binding)
        local g = geometry(source, parent)
        if not g then self:hide(); return false end
        local dpi = required('/Script/UMG.Default__WidgetLayoutLibrary'):GetViewportScale(source)
        local font_size = math.max(14, math.ceil(14 * dpi / (g.absolute_scale or 1)))
        if self.reading ~= binding.reading or self.font_size ~= font_size then
            local adjusted = label.Font; adjusted.Size = font_size; label:SetFont(adjusted)
            label:SetText(required('/Script/Engine.Default__KismetTextLibrary'):Conv_StringToText(binding.reading))
            self.reading, self.font_size = binding.reading, font_size
            label:ForceLayoutPrepass()
            self.measured = label:GetDesiredSize()
        end
        host:SetVisibility(3)
        local measured = self.measured
        slot:SetPosition({X = g.position.X + (g.size.X * ((binding.left or 0) + (binding.right or 1))/2 - measured.X/2) * g.scale.X,
            Y = g.position.Y + ((binding.top or 0) * g.size.Y - measured.Y + 4 * dpi / (g.absolute_scale or 1)) * g.scale.Y})
        slot:SetSize(measured)
        host:SetRenderTransformPivot({X = 0, Y = 0})
        host:SetRenderScale(g.scale)
        text_slot:SetPosition({X = 0, Y = 0})
        return true
    end
    return result
end

function M.attach(source, options)
    options = options or {}
    assert(valid(source), 'A valid source text widget is required')
    local canvas_class = required('/Script/UMG.CanvasPanel')
    local parent = options.geometry and M.parent_of(source) or source:GetParent()
    while valid(parent) and not parent:IsA(canvas_class) do
        parent = options.geometry and M.parent_of(parent) or parent:GetParent()
    end
    assert(valid(parent), 'The source text has no CanvasPanel ancestor')
    local text_slot = source.Slot
    local anchor_source = source
    local vertical_box_slot
    if not options.geometry and valid(text_slot) and text_slot:IsA('/Script/UMG.VerticalBoxSlot') then
        local box = source:GetParent()
        assert(box:GetChildrenCount() == 1 and box:GetChildAt(0):GetAddress() == source:GetAddress(),
            'Only a single-text VerticalBox can host choice ruby')
        anchor_source, vertical_box_slot = box, text_slot
    end
    local source_slot = anchor_source.Slot
    assert(options.geometry or (valid(source_slot) and source_slot:IsA('/Script/UMG.CanvasPanelSlot')),
        'The source text or its single-child VerticalBox must occupy a CanvasPanelSlot')
    local self = setmetatable({
        source = source, source_name = source:GetFullName(), source_slot = source_slot, anchor_source = anchor_source,
        vertical_box_slot = vertical_box_slot, parent = parent, outer = source:GetOuter(),
        options = options, widgets = {}, widths = {}, width_keys = {}, width_cursor = 1,
        heights = {}, previous_text = nil,
        shifted_slots = {}, native_images = {},
        text_class = required('/Script/UMG.TextBlock'),
        text_library = required('/Script/Engine.Default__KismetTextLibrary'),
        layout_library = required('/Script/UMG.Default__WidgetLayoutLibrary'),
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
    self.font_size = options.fixed_base_size or self.font_size
    -- The fallback font holder is also used for measurement, so its live font
    -- struct can change. Preserve the base outline before measuring any ruby.
    self.base_outline = tonumber(self.font.OutlineSettings.OutlineSize) or 0
    self.host = create(canvas_class, self.outer)
    self.host_name = self.host:GetFullName()
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
    -- A padded ruby-only host may cross a label's decorative clip rectangle.
    -- Log rows keep their native ScrollBox clipping instead.
    self.canvas:SetClipping(options.pad_overlay and (M.scroll_parent(source) and 1 or 2) or options.overlay_only and 0 or 1)
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
    font.OutlineSettings.OutlineSize = role == 'ruby' and (self.options.ruby_outline or 0) or
        self.options.overlay_only and 0 or self.base_outline
    if role == 'ruby' and self.options.ruby_outline and self.color then
        local color, outline = self.color.SpecifiedColor, font.OutlineSettings.OutlineColor
        local shade = (color.R + color.G + color.B) / 3 > 0.6 and 0.03 or 1
        outline.R, outline.G, outline.B, outline.A = shade, shade, shade, 0.9
    end
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
        local size_box = self.measure_widget:GetDesiredSize()
        self.measure_widget:SetVisibility(1)
        -- Font/style belong to this renderer; widths are in local Slate units,
        -- independent of viewport scaling. Keep at most 2048 measured strings.
        local expired = self.width_keys[self.width_cursor]
        if expired then self.widths[expired] = nil end
        self.width_keys[self.width_cursor] = key
        self.width_cursor = self.width_cursor % 2048 + 1
        self.widths[key] = size_box.X
        self.heights[font_key] = math.max(self.heights[font_key] or 0, size_box.Y)
        if self.options and self.options.yield_work then self.options.yield_work() end
    end
    return self.widths[key]
end

function Renderer:_anchor_size()
    if self.options.geometry then return self.options.geometry(self.source, self.parent).size end
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
    if self.options.geometry then
        local geometry = self.options.geometry(self.source, self.parent)
        assert(geometry, 'Source geometry is not ready')
        local key = string.format('%.2f:%.2f:%.2f:%.2f:%.4f:%.4f',geometry.position.X,geometry.position.Y,
            geometry.size.X,geometry.size.Y,geometry.scale.X,geometry.scale.Y)
        if self.sync_geometry_key == key then return end
        self.sync_geometry_key = key
        local padding = self.options.pad_overlay and 32 or 0
        self.slot:SetAnchors({Minimum = {X = 0, Y = 0}, Maximum = {X = 0, Y = 0}})
        self.slot:SetAlignment({X = 0, Y = 0})
        self.slot:SetPosition({X = geometry.position.X - padding * geometry.scale.X,
            Y = geometry.position.Y - padding * geometry.scale.Y})
        self.slot:SetSize({X = geometry.size.X + padding * 2, Y = geometry.size.Y + padding})
        self.slot:SetAutoSize(false)
        self.host:SetRenderTransformPivot({X = 0, Y = 0})
        self.host:SetRenderScale(geometry.scale or {X = 1, Y = 1})
        return
    end
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

function Renderer:_pooled(index, reading)
    if not self.widgets[index] then
        if self.options and self.options.overlay_only then
            self.widgets[index] = {}
        else
            local base, base_slot = self:_text_widget()
            self.widgets[index] = {base = base, base_slot = base_slot}
        end
    end
    local pair = self.widgets[index]
    if reading and not pair.ruby then pair.ruby, pair.ruby_slot = self:_text_widget() end
    return pair
end

function Renderer:_source_visible()
    local widget = self.source
    while valid(widget) do
        if not widget:IsVisible() then return false end
        if widget:GetAddress() == self.parent:GetAddress() then break end
        widget = self.options.geometry and M.parent_of(widget) or widget:GetParent()
    end
    return true
end

function Renderer:_expanded_size(size)
    if not self.options.expand_dialogue then return size end
    local library = self.layout_library
    local viewport = library:GetViewportSize(self.source)
    local scale = library:GetViewportScale(self.source)
    assert(scale and scale > 0 and viewport.X > 0 and viewport.Y > 0, 'Viewport is not ready')
    local width = viewport.X / scale * 0.67
    if valid(self.parent.Slot) and self.parent.Slot:IsA('/Script/UMG.CanvasPanelSlot') then
        width = self.parent.Slot:GetSize().X
    end
    return {X = math.min(width, viewport.X / scale * 0.90), Y = viewport.Y / scale * 0.22}
end

function Renderer:_expand_plate(original, size)
    if not self.options.expand_dialogue then return end
    local alignment, position = self.source_slot:GetAlignment(), self.source_slot:GetPosition()
    local extra = size.Y - original.Y
    self.slot:SetSize(size)
    self.slot:SetPosition({X = position.X + (alignment.X - 0.5) * (size.X - original.X),
        Y = position.Y - (1 - alignment.Y) * extra})
    local owner = self.options.owner
    if valid(owner) and not self.images_saved then
        local function visit(widget, depth)
            if not valid(widget) or M.is_generated(widget) or depth > 8 then return end
            if widget:IsA('/Script/UMG.BackgroundBlur') and valid(widget.Slot) and
                widget.Slot:IsA('/Script/UMG.CanvasPanelSlot') then
                local slot = widget.Slot
                local anchors, alignment = slot:GetAnchors(), slot:GetAlignment()
                local position, size = slot:GetPosition(), slot:GetSize()
                self.native_blur = {slot = slot, auto = slot.bAutoSize,
                    anchors = {Minimum = {X = anchors.Minimum.X, Y = anchors.Minimum.Y},
                        Maximum = {X = anchors.Maximum.X, Y = anchors.Maximum.Y}},
                    alignment = {X = alignment.X, Y = alignment.Y},
                    position = {X = position.X, Y = position.Y}, size = {X = size.X, Y = size.Y}}
            end
            local name = widget:GetFName():ToString()
            if name == 'Windows' then
                -- The background contains all native window variants.
                self.native_images[#self.native_images + 1] = {
                    widget = widget, opacity = widget.RenderOpacity, visibility = widget.Visibility,
                }
                return
            end
            if widget:IsA('/Script/UMG.Image') then
                local resource = widget.Brush.ResourceObject
                local name = valid(resource) and resource:GetFullName():lower() or ''
                if name:find('wt_message_window', 1, true) or name:find('wt_mes_cursor', 1, true) then
                    -- Native wait/animation can show a cursor container again.
                    -- Collapse its leaf images so its plate cannot leak below us.
                    self.native_images[#self.native_images + 1] = {
                        widget = widget, opacity = widget.RenderOpacity, visibility = widget.Visibility,
                    }
                end
            end
            local ok, count = pcall(function() return widget:GetChildrenCount() end)
            if ok then for index = 0, count - 1 do visit(widget:GetChildAt(index), depth + 1) end end
        end
        visit(self.parent, 0)
        local ok, cursor = pcall(function() return owner._PanelCursor end)
        if ok and valid(cursor) then
            self.native_images[#self.native_images + 1] = {widget = cursor, opacity = cursor.RenderOpacity}
        end
        self.images_saved = true
    end
    if not self.backgrounds then
        self.backgrounds = {}
        -- This texture is one half of the native window. Mirror the second
        -- half, as the original HorizontalBox does, to keep both rounded ends.
        local texture = LoadAsset('/Game/Widget/Commu/Textures/WT_message_window.WT_message_window')
        assert(valid(texture), 'The original dialogue background is unavailable')
        for index = 1, 2 do
            local image = create(required('/Script/UMG.Image'), self.outer)
            image:SetBrushFromTexture(texture, false)
            image:SetVisibility(3)
            if index == 2 then
                image:SetRenderTransformPivot({X = 0.5, Y = 0.5})
                image:SetRenderScale({X = -1, Y = 1})
            end
            local slot = self.canvas:AddChildToCanvas(image)
            slot:SetZOrder(-10)
            self.backgrounds[index] = {widget = image, slot = slot}
        end
    end
    for index, background in ipairs(self.backgrounds) do
        background.slot:SetPosition({X = (index - 1) * size.X / 2, Y = 0})
        background.slot:SetSize({X = size.X / 2, Y = size.Y})
    end
    if self.native_blur and valid(self.native_blur.slot) then
        -- Keep the original blur inside the resized window instead of leaving
        -- a blurred strip at the old lower edge. Native inset is ten units.
        local slot = self.native_blur.slot
        local alignment, position = self.slot:GetAlignment(), self.slot:GetPosition()
        slot:SetAnchors(self.slot:GetAnchors())
        slot:SetAlignment(alignment)
        slot:SetPosition({X = position.X + (1 - 2 * alignment.X) * 10,
            Y = position.Y + (1 - 2 * alignment.Y) * 10})
        slot:SetSize({X = size.X - 20, Y = size.Y - 20})
        slot:SetAutoSize(false)
    end
    for _, image in ipairs(self.native_images) do
        if valid(image.widget) then
            image.widget:SetRenderOpacity(0)
            if image.visibility then image.widget:SetVisibility(1) end -- Native cursor animations can reset opacity.
        end
    end
    if valid(owner) and not self.slots_saved then
        for _, name in ipairs({'_WidgetName', '_PanelGuide'}) do
            local ok, widget = pcall(function() return owner[name] end)
            if ok and valid(widget) and valid(widget.Slot) and widget.Slot:IsA('/Script/UMG.CanvasPanelSlot') then
                local p = widget.Slot:GetPosition()
                self.shifted_slots[#self.shifted_slots + 1] = {
                    slot = widget.Slot, widget = widget, clipping = widget.Clipping,
                    x = p.X, y = p.Y, name = name == '_WidgetName',
                }
            end
        end
        self.slots_saved = true
    end
    for _, saved in ipairs(self.shifted_slots) do
        if valid(saved.slot) then
            local shift_x = 0
            if saved.name then
                -- Both native message panels are centered. Align the header
                -- with the expanded panel and clip its decorative curl, which
                -- otherwise extends below the header's 62-unit bounds.
                local parent_slot = self.parent.Slot
                if valid(parent_slot) and parent_slot:IsA('/Script/UMG.CanvasPanelSlot') then
                    shift_x = (parent_slot:GetSize().X - size.X) / 2
                end
                saved.widget:SetClipping(1)
            end
            saved.slot:SetPosition({X = saved.x + shift_x, Y = saved.y - extra + 32})
        end
    end
end

function Renderer:geometry_key()
    if not self:_valid_source() or not valid(self.parent) then return nil end
    if self.options.geometry then
        local g = self.options.geometry(self.source, self.parent)
        if not g then return nil end
        -- Position changes need only follow the native slot, not measure again.
        self:_sync_slot()
        return string.format('%.1f:%.1f:%.3f:%.3f:%.3f', g.size.X, g.size.Y, g.scale.X, g.scale.Y,
            g.absolute_scale or 1)
    end
    local layout = self.source_slot.LayoutData
    local o, a, n, x = layout.Offsets, layout.Alignment, layout.Anchors.Minimum, layout.Anchors.Maximum
    local t = self.source.RenderTransform
    local padding = self:_padding()
    local size = self:_expanded_size(self:_size())
    return string.format('%.2f:%.2f:%.2f:%.2f:%.2f:%.2f:%.3f:%.3f:%.3f:%.3f:%.2f:%.2f:%.3f:%.3f:%.3f:%.2f:%.2f:%.2f:%.2f:%s',
        o.Left, o.Top, size.X, size.Y, a.X, a.Y, n.X, n.Y, x.X, x.Y,
        t.Translation.X, t.Translation.Y, t.Scale.X, t.Scale.Y, t.Angle,
        padding.Left, padding.Top, padding.Right, padding.Bottom, tostring(self:_source_visible())) ..
        ':' .. tostring(self.layout_library:GetViewportScale(self.source))
end

function Renderer:_valid_source()
    return valid(self.source) and self.source:GetFullName() == self.source_name
end

function Renderer:_valid_host()
    return valid(self.host) and self.host:GetFullName() == self.host_name
end

function Renderer:hide()
    if self:_valid_host() then self.host:SetVisibility(1) end
    if not self:_valid_source() then self.previous_text = nil; return end
    self.source:SetRenderOpacity(self.original_opacity)
    local blur = self.native_blur
    if blur and valid(blur.slot) then
        blur.slot:SetAnchors(blur.anchors)
        blur.slot:SetAlignment(blur.alignment)
        blur.slot:SetPosition(blur.position)
        blur.slot:SetSize(blur.size)
        blur.slot:SetAutoSize(blur.auto)
    end
    for _, saved in ipairs(self.shifted_slots) do
        if valid(saved.slot) then saved.slot:SetPosition({X = saved.x, Y = saved.y}) end
        if valid(saved.widget) then saved.widget:SetClipping(saved.clipping) end
    end
    for _, image in ipairs(self.native_images) do
        if valid(image.widget) then
            image.widget:SetRenderOpacity(image.opacity)
            if image.visibility then image.widget:SetVisibility(image.visibility) end
        end
    end
    self.previous_text = nil
end

function Renderer:detach()
    self:hide()
    if self:_valid_host() then self.host:RemoveFromParent() end
end

function Renderer:update(segments, visible_count)
    if not self:_valid_source() or not valid(self.parent) then return false, 'Source widget expired' end
    if not self.options.prepare_hidden and not self:_source_visible() then self:hide(); return false, 'Source widget or its ancestor is hidden' end
    local source_text = Layout.text(segments)
    if source_text:find('<[^>]+>') then
        self:hide()
        return false, 'Rich-text markup requires a style-preserving parser'
    end
    local scale = self.layout_library:GetViewportScale(self.source)
    if self.measure_scale ~= scale then
        self.widths, self.width_keys, self.width_cursor, self.heights = {}, {}, 1, {}
        self.measure_scale = scale
    end
    local original_size = self:_size()
    local size = self:_expanded_size(original_size)
    if size.X <= 0 or size.Y <= 0 then
        self:hide(); return false, 'Source geometry is not ready'
    end
    self:_sync_slot()
    self:_expand_plate(original_size, size)
    -- Hidden canvases may retain stale desired sizes. Measure while visible but
    -- fully transparent; swap to generated text only after a successful layout.
    self.host:SetVisibility(3)
    self.host:SetRenderOpacity(0)
    local margin = self.source.Margin
    if self.options.expand_dialogue then
        margin = {Left = 36, Right = 36, Top = 14, Bottom = 38}
        local ok, npc = pcall(function() return self.options.owner._WidgetNPC end)
        if ok and valid(npc) and npc:IsVisible() and npc.RenderOpacity > 0.01 then margin.Left = 340 end
    end
    self.active_margin = margin
    self.active_size = size
    local width = self.options.width or math.max(1, size.X - margin.Left - margin.Right)
    local original_height = math.max(1, size.Y - margin.Top - margin.Bottom)
    if self.options.pad_overlay then
        self.active_margin = {Left = margin.Left + 32, Top = margin.Top + 32, Right = margin.Right, Bottom = margin.Bottom}
    end
    local slack = math.max(0, self.options.max_vertical_slack or 0)
    local height = original_height + slack
    local minimum = self.options.fixed_size and self.font_size or math.min(self.font_size, self.options.min_base_size or 18)
    local min_ruby = self.options.min_ruby_size or 8
    if self.options.geometry then
        local g = self.options.geometry(self.source, self.parent)
        if g and g.absolute_scale and g.absolute_scale > 0 then min_ruby = math.ceil(min_ruby * scale / g.absolute_scale) end
    end
    local result
    for base_size = self.font_size, minimum, -1 do
        local ruby_size = math.max(min_ruby, math.floor(base_size * (self.options.ruby_scale or (self.options.fixed_size and 0.5 or 0.48))))
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
            overlay_only = self.options.overlay_only,
            native_line_height = base_height * (tonumber(self.source.LineHeightPercentage) or 1),
            no_wrap = self.options.overlay_only and not self.source.AutoWrapText and (tonumber(self.source.WrapTextAt) or 0) <= 0,
        })
        result.fit_summary = string.format('base=%d ruby=%d lines=%d height=%.2f/%.2f baseH=%.2f rubyH=%.2f width=%.2f',
            base_size, ruby_size, result.lines, result.height, height, base_height, ruby_height, width)
        if result.height <= height then break end
    end
    if not result or (result.height > height and not self.options.paginate and not self.options.overlay_only and not self.options.grow) then
        self:hide(); return false, 'Ruby does not fit the source rectangle at the minimum readable font size; ' ..
            (result and result.fit_summary or 'no layout result')
    end
    for _, run in ipairs(result.runs) do
        if run.width > width and not self.options.overlay_only then self:hide(); return false, 'A word group exceeds the fixed layout width' end
    end
    if self.options.paginate then
        local pages, reason = Layout.paginate(result, height)
        if not pages then self:hide(); return false, reason end
        self.pages = pages
    else
        result.base_text = source_text
        self.pages = {result}
    end
    self.current_layout = result
    self.original_height = original_height
    self.source_text = source_text
    if self.options.grow then self.options.grow(result.height + margin.Top + margin.Bottom) end
    self:show_page(1)
    return true, result
end

function Renderer:show_page(number)
    assert(self:_valid_source() and valid(self.parent), 'Source widget expired')
    local result = assert(self.pages[number], 'Invalid dialogue page')
    self.page_index = number
    local margin, original_height = self.active_margin, self.original_height
    if not self.options.expand_dialogue and not self.options.geometry and not self.options.overlay_only then
        local added_height = math.max(0, math.ceil(result.height - original_height))
        if added_height > 0 then
            local alignment = self.source_slot:GetAlignment()
            local position = self.source_slot:GetPosition()
            local size = self:_size()
            self.slot:SetSize({X = size.X, Y = size.Y + added_height})
            self.slot:SetPosition({X = position.X, Y = position.Y + added_height * alignment.Y})
        end
    end
    local vertical_offset = 0
    if self.vertical_box_slot then
        local alignment = tonumber(self.vertical_box_slot.VerticalAlignment)
        if alignment == 2 then vertical_offset = math.max(0, original_height - result.height) / 2 end
        if alignment == 3 then vertical_offset = math.max(0, original_height - result.height) end
    end
    for index, run in ipairs(result.runs) do
        local pair = self:_pooled(index, run.reading)
        local changed = false
        local base_size = run.base_size
        local ruby_size_scaled = run.ruby_size
        if pair.base and (pair.base_text ~= run.base or pair.base_size ~= base_size) then
            self:_set_text(pair.base, run.base, base_size, 'base')
            pair.base_text, pair.base_size = run.base, base_size
            changed = true
        end
        local base_x, base_y = margin.Left + run.x, margin.Top + vertical_offset + run.y
        if pair.base_slot and (pair.base_x ~= base_x or pair.base_y ~= base_y) then
            pair.base_slot:SetPosition({X = base_x, Y = base_y})
            pair.base_x, pair.base_y = base_x, base_y
            changed = true
        end
        local base_visible = not self.options.overlay_only
        if pair.base and pair.base_visible ~= base_visible then
            pair.base:SetVisibility(base_visible and 3 or 1)
            pair.base_visible, changed = base_visible, true
        end
        if run.reading then
            if pair.ruby_text ~= run.reading or pair.ruby_size ~= ruby_size_scaled then
                self:_set_text(pair.ruby, run.reading, ruby_size_scaled, 'ruby')
                pair.ruby_text, pair.ruby_size = run.reading, ruby_size_scaled
                changed = true
            end
            local ruby_x, ruby_y = margin.Left + run.ruby_x, margin.Top + vertical_offset + run.ruby_y
            if pair.ruby_x ~= ruby_x or pair.ruby_y ~= ruby_y then
                pair.ruby_slot:SetPosition({X = ruby_x, Y = ruby_y})
                pair.ruby_x, pair.ruby_y = ruby_x, ruby_y
                changed = true
            end
            if pair.ruby_visible ~= true then
                pair.ruby:SetVisibility(3)
                pair.ruby_visible, changed = true, true
            end
        elseif pair.ruby and pair.ruby_visible ~= false then
            pair.ruby:SetVisibility(1)
            pair.ruby_visible, changed = false, true
        end
        -- Checkpoint only after storing completed work. Retrying cached runs
        -- must not spend the budget repeating native visibility setters, or a
        -- long row can yield forever without reaching its remaining runs.
        if changed and self.options.yield_work then self.options.yield_work() end
    end
    for index = #result.runs + 1, #self.widgets do
        local pair = self.widgets[index]
        if pair.base then pair.base:SetVisibility(1); pair.base_visible = false end
        if pair.ruby then pair.ruby:SetVisibility(1); pair.ruby_visible = false end
    end
    if self.options.expand_dialogue then
        if not self.page_indicator then self.page_indicator, self.indicator_slot = self:_text_widget() end
        self:_set_text(self.page_indicator, #self.pages > 1 and string.format('%d / %d  >', number, #self.pages) or '>', 14, 'ruby')
        self.indicator_slot:SetPosition({X = self.active_size.X - 150, Y = self.active_size.Y - 70})
    end
    self.host:SetVisibility(3)
    self.host:SetRenderOpacity(1)
    if not self.options.overlay_only then self.source:SetRenderOpacity(0) end
    self.previous_text = self.source_text
    return true
end

return M
