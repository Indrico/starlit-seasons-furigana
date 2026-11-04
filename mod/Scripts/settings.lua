-- User preferences are data, not executable Lua, and are outside owned scripts.
local M = {}
function M.load(path)
    local values = {enabled = true, manual = true, auto_min_seconds = 3, auto_characters_per_second = 8}
    local file = io.open(path, 'r')
    if file then
        for line in file:lines() do
            local key, value = line:match('^%s*([%w_]+)%s*=%s*([^#;]+)')
            if key == 'manual' or key == 'enabled' then
                value = value:match('^%s*(.-)%s*$')
                if value == 'true' or value == 'false' then values[key] = value == 'true' end
            elseif key == 'auto_min_seconds' or key == 'auto_characters_per_second' then
                local number = tonumber(value)
                if number and number == number and number >= 1 and number <= 60 then values[key] = number end
            end
        end
        file:close()
    end
    return values
end
function M.save(path, values)
    local file, message = io.open(path, 'w')
    if not file then return false, message end
    local ok, error_message = file:write(string.format('enabled = %s\nmanual = %s\nauto_min_seconds = %.3f\nauto_characters_per_second = %.3f\n',
        tostring(values.enabled ~= false), tostring(values.manual), values.auto_min_seconds, values.auto_characters_per_second))
    file:close()
    return ok ~= nil, error_message
end
return M
