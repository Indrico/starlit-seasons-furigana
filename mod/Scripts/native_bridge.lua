-- No Lua ABI imports are needed by these zero-result native entry points.
local M = {}
function M.load(directory)
    local result = {}
    for _, name in ipairs({'initialize', 'manual', 'auto', 'hold', 'release', 'enable', 'disable'}) do
        local fn, message = package.loadlib(directory .. 'StarlitFuriganaNative.dll', 'sf_' .. name)
        if not fn then return nil, message end
        result[name] = fn
    end
    return result
end
return M
