-- A native clickable control attached to the game's Options menu.
local M = {}
local Menu = {}
Menu.__index = Menu
local function valid(object) return object and object:IsValid() end
local function required(path)
    local object = StaticFindObject(path)
    assert(valid(object), 'Menu object unavailable: ' .. path)
    return object
end
local function canvas(widget, depth)
    if not valid(widget) or depth > 8 then return nil end
    if widget:IsA('/Script/UMG.CanvasPanel') then return widget end
    local ok, count = pcall(function() return widget:GetChildrenCount() end)
    if ok then
        for index = 0, count - 1 do
            local found = canvas(widget:GetChildAt(index), depth + 1)
            if found then return found end
        end
    end
end
function M.new(settings, toggle)
    return setmetatable({settings = settings, toggle = toggle, entries = {}}, Menu)
end
function Menu:attach(owner)
    local root = canvas(owner.WidgetTree.RootWidget, 0)
    assert(root, 'Options has no supported canvas')
    local button = StaticConstructObject(required('/Script/imal.HitAreaWidget'), owner)
    -- HitAreaWidget binds its native input delegates when registered with a
    -- checker. Its checker pointer is not reflected, so root one checker for
    -- the process lifetime using RF_MarkAsRootSet, without async-loading flags.
    if not self.checker then
        self.checker = StaticConstructObject(required('/Script/imal.HitAreaChecker'), FindFirstOf('GameInstance'), 0, 0x80)
    end
    self.checker:AddHitArea(button, 1)
    local label = StaticConstructObject(required('/Script/UMG.TextBlock'), owner)
    local font = label.Font
    font.FontObject = LoadAsset('/Game/Widget/Font/FONT-JP.FONT-JP')
    font.TypefaceFontName, font.Size = FName('Text'), 24
    label:SetFont(font)
    label:SetColorAndOpacity({SpecifiedColor = {R = 0.03, G = 0.03, B = 0.03, A = 1}, ColorUseRule = 0})
    label:SetVisibility(3)
    button:SetRenderOpacity(1)
    button:SetStyle(required('/Script/UMG.Default__Button').WidgetStyle)
    button:SetColorAndOpacity({R = 1, G = 1, B = 1, A = 1})
    button:SetBackgroundColor({R = 0.9, G = 0.95, B = 0.95, A = 1})
    button.IsFocusable = true
    button:AddChild(label)
    local slot = root:AddChildToCanvas(button)
    slot:SetAnchors({Minimum = {X = 1, Y = 1}, Maximum = {X = 1, Y = 1}})
    slot:SetAlignment({X = 1, Y = 1})
    slot:SetPosition({X = -80, Y = -90})
    slot:SetSize({X = 520, Y = 64})
    slot:SetZOrder(2000)
    button:SetVisibility(0)
    print('[StarlitFurigana] Options toggle attached to ' .. root:GetFullName() .. '\n')
    return {owner = owner, button = button, label = label}
end
function Menu:tick()
    for address, entry in pairs(self.entries) do
        if not valid(entry.owner) or not valid(entry.button) then self.entries[address] = nil end
    end
    for _, owner in ipairs(FindAllOf('WidgetOptionTop') or {}) do
        if valid(owner) and owner:IsInViewport() and owner:IsVisible() and
            owner:GetFullName():find('/Engine/Transient.', 1, true) then
            local address = owner:GetAddress()
            if not self.entries[address] then self.entries[address] = self:attach(owner) end
        end
    end
    local text_library = next(self.entries) and required('/Script/Engine.Default__KismetTextLibrary')
    for _, entry in pairs(self.entries) do
        if entry.owner:IsVisible() and entry.button:GetOnClickedSignal(true) then
            self.toggle(self.settings.enabled == false)
        end
        local state = self.settings.enabled ~= false
        if entry.state ~= state then
            entry.label:SetText(text_library:Conv_StringToText('Furigana Mod: ' .. (state and 'ON' or 'OFF') .. '  [F8]'))
            entry.state = state
        end
    end
end
function Menu:toggle_visible()
    for _, entry in pairs(self.entries) do
        if valid(entry.owner) and entry.owner:IsVisible() then
            self.toggle(self.settings.enabled == false)
            return true
        end
    end
    return false
end
return M
