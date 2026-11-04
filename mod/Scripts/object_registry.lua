-- One initial snapshot, then construction notifications. Drain on the game thread:
-- notification callbacks can run before reflected fields have been initialized.
local M = {}
function M.new(classes, accept)
    local self = {pending = {}, entries = {}, names = {}, classes = classes}
    if NotifyOnNewObject then
        for _, class in ipairs(classes) do
            NotifyOnNewObject(class, function(object)
                self.pending[#self.pending + 1] = object
            end)
        end
    end
    function self:objects()
        if not self.initialized then
            self.initialized = true
            for _, class in ipairs(self.classes) do
                for _, object in ipairs(FindAllOf(class:match('%.([^%.]+)$') or class) or {}) do
                    self.pending[#self.pending + 1] = object
                end
            end
        end
        local pending = self.pending
        self.pending = {}
        for _, object in ipairs(pending) do
            if object:IsValid() and (not accept or accept(object)) then
                local address = object:GetAddress()
                self.entries[address], self.names[address] = object, object:GetFullName()
            end
        end
        for address, object in pairs(self.entries) do
            if not object:IsValid() or object:GetFullName() ~= self.names[address] then
                self.entries[address], self.names[address] = nil, nil
            end
        end
        return self.entries
    end
    function self:find(address)
        local object = self:objects()[address]
        if object then return object end
        -- A native assignment can precede UE4SS's queued construction callback.
        -- Recover only on that miss, without scanning all text widgets.
        for _, class in ipairs(self.classes) do
            for _, candidate in ipairs(FindAllOf(class:match('%.([^%.]+)$') or class) or {}) do
                if candidate:IsValid() and candidate:GetAddress() == address and (not accept or accept(candidate)) then
                    self.entries[address], self.names[address] = candidate, candidate:GetFullName()
                    return candidate
                end
            end
        end
    end
    return self
end
return M
