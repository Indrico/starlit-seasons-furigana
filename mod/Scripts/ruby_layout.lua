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
local function units(segments, chunk_plain)
    local out, consumed = {}, 0
    for _, segment in ipairs(segments) do
        local reading = segment.reading
        if reading and reading ~= '' then
            assert(not segment.base:find('[\r\n]'), 'Ruby must not span a newline')
            out[#out + 1] = {base = segment.base, reading = reading, start = consumed}
            consumed = consumed + utf8.len(segment.base)
        elseif chunk_plain then
            -- Ruby-only, non-wrapping labels need advances at span boundaries,
            -- not a separate native font prepass for every kana character.
            for text, breaks in segment.base:gmatch('([^\r\n]*)([\r\n]*)') do
                if text ~= '' then
                    out[#out + 1] = {base = text, start = consumed}
                    consumed = consumed + utf8.len(text)
                end
                for _, character in ipairs(chars(breaks)) do
                    out[#out + 1] = {base = character, start = consumed}
                    consumed = consumed + 1
                end
            end
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
    local line_height = options.overlay_only and (options.native_line_height or base_height) or
        base_height + ruby_height + gap + line_gap
    local visible = options.visible_count or math.huge
    if options.overlay_only then
        -- Adjacent annotated compounds share a reading lane. Their native
        -- glyph advances stay unchanged; separate centered labels could
        -- otherwise collide on small menu captions.
        local combined = {}
        for _, segment in ipairs(segments) do
            local previous = combined[#combined]
            if segment.reading and previous and previous.reading then
                previous.base = previous.base .. segment.base
                previous.reading = previous.reading .. segment.reading
            else
                combined[#combined+1] = {base=segment.base,reading=segment.reading}
            end
        end
        segments = combined
    end
    local items = units(segments, options.overlay_only and options.no_wrap)
    local prefix, prefix_width = '', 0
    for _, item in ipairs(items) do
        if item.base == '\r' or item.base == '\n' then
            item.base_width, item.ruby_width, item.width = 0, 0, 0
            prefix, prefix_width = '', 0
        else
            if options.overlay_only then
                prefix = prefix .. item.base
                local next_width = options.measure(prefix, base_size, 'base')
                item.base_width, prefix_width = next_width - prefix_width, next_width
            else
                item.base_width = options.measure(item.base, base_size, 'base')
            end
            item.ruby_width = item.reading and options.measure(item.reading, ruby_size, 'ruby') or 0
            item.width = options.overlay_only and item.base_width or math.max(item.base_width, item.ruby_width)
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
            if not options.no_wrap and x > 0 and x + needed > options.width and not closing[cp] then newline() end
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
                    y = options.overlay_only and y or y + ruby_height + gap,
                    ruby_x = x + (item.width - item.ruby_width) / 2,
                    ruby_y = options.overlay_only and y - ruby_height - gap or y,
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
        line_gap = line_gap, lines = line, line_widths = line_widths}
end

-- Collapse plain log runs only when the native combined width agrees with the
-- existing advances. Keep separately positioned runs when kerning would move them.
function M.compact_plain(result, measure)
    local runs, index = {}, 1
    while index <= #result.runs do
        local first, last = result.runs[index], index
        if not first.reading then
            while last < #result.runs do
                local current, next_run = result.runs[last], result.runs[last + 1]
                if next_run.reading or next_run.line ~= first.line or next_run.base_size ~= first.base_size or
                    math.abs(current.x + current.base_width - next_run.x) > 0.01 then break end
                last = last + 1
            end
        end
        if last > index then
            local parts = {}
            for i = index, last do parts[#parts + 1] = result.runs[i].base end
            local text = table.concat(parts)
            local width = result.runs[last].x + result.runs[last].base_width - first.x
            if math.abs(measure(text, first.base_size, 'base') - width) <= 0.01 then
                local run = {}
                for key, value in pairs(first) do run[key] = value end
                run.base, run.base_width, run.width = text, width, width
                runs[#runs + 1] = run
            else
                for i = index, last do runs[#runs + 1] = result.runs[i] end
            end
        else
            runs[#runs + 1] = first
        end
        index = last + 1
    end
    result.runs = runs
    return result
end

function M.paginate(result, height)
    local lines_per_page = math.floor((height + result.line_gap) / result.line_height)
    if lines_per_page < 1 then return nil, 'One line does not fit at the fixed font size' end
    local pages = {}
    for number = 1, math.ceil(result.lines / lines_per_page) do
        local first = (number - 1) * lines_per_page + 1
        local last = math.min(result.lines, first + lines_per_page - 1)
        local page = {runs = {}, base_text = '', lines = last - first + 1,
            height = (last - first + 1) * result.line_height - result.line_gap}
        for _, run in ipairs(result.runs) do
            if run.line >= first and run.line <= last then
                local copy = {}
                for key, value in pairs(run) do copy[key] = value end
                copy.y, copy.ruby_y = run.y - (first - 1) * result.line_height, run.ruby_y - (first - 1) * result.line_height
                copy.line = run.line - first + 1
                page.runs[#page.runs + 1] = copy
                page.base_text = page.base_text .. copy.base
            end
        end
        pages[#pages + 1] = page
    end
    return pages
end

return M
