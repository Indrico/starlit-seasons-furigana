-- LiveManager exists for the performance, including its pause/photo menus.
-- One initial snapshot plus construction notifications; never scan per frame.
local M = {}
function M.new(clock, changed)
    local owners = require('object_registry').new({'/Script/imal.LiveManager'}, function(object)
        return object:GetFullName():find(':PersistentLevel.', 1, true) ~= nil
    end)
    local self = {active = false, next_check = 0}
    function self:poll(force)
        local now = clock()
        if not force and now < self.next_check then return self.active end
        self.next_check = now + 0.25
        local active = next(owners:objects()) ~= nil
        if active ~= self.active then
            self.active = active
            changed(active)
        end
        return self.active
    end
    return self
end
return M
