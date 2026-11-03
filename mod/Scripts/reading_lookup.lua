-- Release data contains only source hashes, UTF-8 byte spans, and kana readings.
-- Base text always comes from the game's current widget.
local SHA256 = require('sha256')
local M = {}

function M.get(database, text)
    if database.format == nil then return database[text] end -- Private legacy table.
    if database.format ~= 'starlit-furigana-spans-v1' then return nil end
    local entry = database.entries[SHA256.hex(text)]
    if not entry or entry.n ~= #text then return nil end
    local segments, cursor = {}, 1
    for _, span in ipairs(entry.s) do
        local first, length, reading = span[1], span[2], span[3]
        if math.type(first) ~= 'integer' or math.type(length) ~= 'integer' or
            first < cursor or length < 1 or first + length - 1 > #text then return nil end
        local plain, base = text:sub(cursor, first - 1), text:sub(first, first + length - 1)
        if not utf8.len(plain) or not utf8.len(base) then return nil end
        if #plain > 0 then segments[#segments + 1] = {base = plain} end
        local segment = {base = base}
        if reading == false then segment.control = true
        elseif type(reading) == 'string' and #reading > 0 then segment.reading = reading
        else return nil end
        segments[#segments + 1] = segment
        cursor = first + length
    end
    local tail = text:sub(cursor)
    if not utf8.len(tail) then return nil end
    if #tail > 0 then segments[#segments + 1] = {base = tail} end
    return segments
end
return M
