-- One initial snapshot, then construction notifications. Drain on the game thread:
-- notification callbacks can run before reflected fields have been initialized.
local M = {}
function M.new(classes, accept, options)
    local self = {pending = {}, entries = {}, names = {}, classes = classes, added = {}, options = options or {}}
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
        if not self.batch then
            self.batch, self.pending, self.batch_cursor = self.pending, {}, 1
        end
        -- Live construction must not wait behind a large initial snapshot.
        -- Keep the snapshot cursor and give new notifications a bounded turn.
        local fresh = self.options.incremental and self.batch_cursor > 1 and #self.pending > 0
        local pending = fresh and self.pending or self.batch
        local first = fresh and math.max(1, #pending - (self.options.admit_limit or #pending) + 1) or self.batch_cursor
        local last = math.min(#pending, first + (self.options.admit_limit or #pending) - 1)
        for index = first, last do
            local object = pending[index]
            if object:IsValid() and (not accept or accept(object)) then
                local address = object:GetAddress()
                if self.options.incremental and self.names[address] ~= object:GetFullName() then
                    self.added[#self.added + 1] = object
                end
                self.entries[address], self.names[address] = object, object:GetFullName()
            end
        end
        if fresh then
            for index = last, first, -1 do pending[index] = nil end
        else
            self.batch_cursor = last + 1
            if self.batch_cursor > #pending then self.batch = nil end
        end
        if not self.options.incremental then for address, object in pairs(self.entries) do
            if not object:IsValid() or object:GetFullName() ~= self.names[address] then
                self.entries[address], self.names[address] = nil, nil
            end
        end end
        return self.entries
    end
    function self:take_new()
        self:objects()
        local added = self.added
        self.added = {}
        return added
    end
    function self:forget(address)
        self.entries[address], self.names[address] = nil, nil
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
