-- Native FGeometry copies avoid the pinned loader's opaque-struct marshalling.
local M = {}
function M.new(bridge)
    local self = {cache = {}}
    function self:begin_frame() self.cache = {} end
    function self:read(widget)
        if not bridge or not bridge.geometry or not widget or not widget:IsValid() then return nil end
        local address = widget:GetAddress()
        if self.cache[address] ~= nil then return self.cache[address] or nil end
        self.fn = self.fn or StaticFindObject('/Script/UMG.Widget:GetCachedGeometry')
        if not self.fn or not self.fn:IsValid() then return nil end
        local g = {bridge.geometry(address, self.fn:GetAddress())}
        if #g ~= 13 or g[1] <= 0 or g[2] <= 0 or g[1] > 100000 or g[2] > 100000 then
            self.cache[address] = false; return nil
        end
        self.cache[address] = g
        return g
    end
    function self:relative(widget, parent)
        local g, p = self:read(widget), self:read(parent)
        if not g or not p then return nil end
        local det = p[8] * p[11] - p[9] * p[10]
        if math.abs(det) < 0.000001 then return nil end
        local dx, dy = g[12] - p[12], g[13] - p[13]
        local xx, xy = (g[8]*p[11]-g[9]*p[10])/det, (g[9]*p[8]-g[8]*p[9])/det
        local yx, yy = (g[10]*p[11]-g[11]*p[10])/det, (g[11]*p[8]-g[10]*p[9])/det
        -- An arbitrary rotated/sheared label keeps native rendering until it
        -- has a calibrated adapter, rather than placing ruby at a wrong point.
        if math.abs(xy) > 0.001 or math.abs(yx) > 0.001 or xx <= 0 or yy <= 0 then return nil end
        return {position = {X = (dx*p[11]-dy*p[10])/det, Y = (dy*p[8]-dx*p[9])/det},
            size = {X = g[1], Y = g[2]}, scale = {X = xx, Y = yy},
            absolute_scale = math.min(math.sqrt(g[8]^2 + g[9]^2), math.sqrt(g[10]^2 + g[11]^2))}
    end
    return self
end
return M
