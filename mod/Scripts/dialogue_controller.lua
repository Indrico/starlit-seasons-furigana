-- Progression state is independent of rendering and native voice playback.
local M = {}
local Controller = {}
Controller.__index = Controller
function M.new(bridge, settings)
    return setmetatable({bridge = bridge, settings = settings, manual = settings.manual, elapsed = 0}, Controller)
end
function Controller:set_manual(value)
    self.manual, self.settings.manual, self.elapsed = value, value, 0
    self.released = false
    self.bridge[value and 'manual' or 'auto']()
    if self.text then self.bridge.hold() end
end
function Controller:set_line(renderer, text)
    self.renderer, self.text, self.elapsed, self.released = renderer, text, 0, false
    self.bridge.hold()
end
function Controller:clear()
    self.renderer, self.text, self.elapsed, self.released = nil, nil, 0, false
end
function Controller:advance()
    local renderer = self.renderer
    if renderer and renderer.page_index < #renderer.pages then
        renderer:show_page(renderer.page_index + 1)
        self.elapsed = 0
        return true
    end
    return false
end
function Controller:tick(delta)
    if self.manual or not self.text or self.released then return end
    self.elapsed = self.elapsed + math.max(0, delta)
    local renderer = self.renderer
    local text = renderer and renderer.pages[renderer.page_index].base_text or self.text
    local clean_text = (text or ''):gsub('%s', '')
    local count = utf8.len(clean_text) or 0
    local delay = math.max(self.settings.auto_min_seconds, count / self.settings.auto_characters_per_second)
    if self.elapsed >= delay then
        if not self:advance() then
            self.released = true
            self.bridge.release()
        end
    end
end
return M
