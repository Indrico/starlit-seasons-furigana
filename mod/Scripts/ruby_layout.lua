-- Pure Lua layout. Positions are expressed in the source widget's local units.
local M = {}

local closing = {}
for _, cp in utf8.codes('、。，．！？：；）」』】〕〉》ぁぃぅぇぉっゃゅょァィゥェォッャュョー') do
    closing[cp] = true
end
local opening = {}
for _, cp in utf8.codes('（「『【〔〈《') do opening[cp] = true end

local function chars(text)
    local out = {}
    for _, cp in utf8.codes(text) do out[#out + 1] = utf8.char(cp) end
    return out
end

function M.text(segments)
    local out = {}
    for _, segment in ipairs(segments) do out[#out + 1] = segment.base end
    return table.concat(out)
end

-- Ruby groups stay atomic; unannotated text can wrap between characters.
local function units(segments)
    local out, consumed = {}, 0
    for _, segment in ipairs(segments) do
        local reading = segment.reading
        if reading and reading ~= '' then
            assert(not segment.base:find('[\r\n]'), 'Ruby must not span a newline')
            out[#out + 1] = {base = segment.base, reading = reading, start = consumed}
            consumed = consumed + utf8.len(segment.base)
        else
            for _, character in ipairs(chars(segment.base)) do
                out[#out + 1] = {base = character, start = consumed}
                consumed = consumed + 1
            end
        end
    end
    return out
end

function M.layout(segments, options)
    assert(options.width and options.width > 0, 'A positive layout width is required')
    assert(type(options.measure) == 'function', 'Font measurement is required')
    local base_size = options.base_size or 28
    local ruby_size = options.ruby_size or math.floor(base_size * 0.48)
    local gap = options.gap or 1
    local line_gap = options.line_gap or 3
    local base_height = options.base_height or base_size * 1.3
    local ruby_height = options.ruby_height or ruby_size * 1.3
    local line_height = base_height + ruby_height + gap + line_gap
    local visible = options.visible_count or math.huge
    local items = units(segments)
    for _, item in ipairs(items) do
        if item.base == '\r' or item.base == '\n' then
            item.base_width, item.ruby_width, item.width = 0, 0, 0
        else
            item.base_width = options.measure(item.base, base_size, 'base')
            item.ruby_width = item.reading and options.measure(item.reading, ruby_size, 'ruby') or 0
            item.width = math.max(item.base_width, item.ruby_width)
        end
    end
    local runs, x, y, line, skip_lf = {}, 0, 0, 1, false
    local line_widths = {}
    local function newline()
        line_widths[line] = x
        x, y, line = 0, y + line_height, line + 1
    end
    for index, item in ipairs(items) do
        if item.base == '\r' or item.base == '\n' then
            if not (item.base == '\n' and skip_lf) then newline() end
            skip_lf = item.base == '\r'
        else
            skip_lf = false
            local cp = utf8.codepoint(item.base)
            local next_item = items[index + 1]
            local needed = item.width
            if opening[cp] and next_item then needed = needed + next_item.width end
            if x > 0 and x + needed > options.width and not closing[cp] then newline() end
            local remaining = math.max(0, visible - item.start)
            local length = utf8.len(item.base)
            if remaining > 0 then
                local base = item.base
                if remaining < length then
                    local cut = utf8.offset(base, remaining + 1)
                    base = base:sub(1, cut - 1)
                end
                runs[#runs + 1] = {
                    base = base,
                    reading = remaining >= length and item.reading or nil,
                    x = x + (item.width - item.base_width) / 2,
                    y = y + ruby_height + gap,
                    ruby_x = x + (item.width - item.ruby_width) / 2,
                    ruby_y = y,
                    base_width = item.base_width,
                    ruby_width = item.ruby_width,
                    width = item.width,
                    base_size = base_size,
                    ruby_size = ruby_size,
                    line = line,
                }
            end
            x = x + item.width
        end
    end
    line_widths[line] = x
    for _, run in ipairs(runs) do
        local available = math.max(0, options.width - line_widths[run.line])
        local offset = options.justification == 1 and available / 2 or
            (options.justification == 2 and available or 0)
        run.x, run.ruby_x = run.x + offset, run.ruby_x + offset
    end
    return {runs = runs, height = y + line_height - line_gap, line_height = line_height,
        lines = line, line_widths = line_widths}
end

return M
