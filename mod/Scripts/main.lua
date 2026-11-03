-- Add ruby after an exact source line has stopped changing for one polling interval.
-- The native renderer handles the original typewriter animation unchanged.
local script = debug.getinfo(1, 'S').source
local directory = script:sub(1, 1) == '@' and script:sub(2):match('^(.*[/\\])') or nil
assert(directory, 'Could not resolve the Furigana script directory')
package.path = directory .. '?.lua;' .. package.path

local Ruby = require('umg_ruby')
local Lookup = require('reading_lookup')
local database = dofile(directory .. 'readings.lua')
local entries = {}
local enabled = true
local queued = false
local iteration = 0
local discovered = false

local function log(message)
    print('[StarlitFurigana] ' .. message .. '\n')
end

local function is_dialogue_source(object)
    local name = object:GetFullName()
    if not name:find('/Engine/Transient.', 1, true) then return false, name end
    local short = object:GetFName():ToString():lower()
    if name:find('WBP_Commu_Message_C', 1, true) and
        (short == 'richtextblock_message' or short == 'richtextblock_monologue') then return true, name end
    if name:find('WBP_Commu_Cinema_C', 1, true) and
        (short == 'richtextblock_cinemamessage' or short == 'textblock_cinemamessage') then return true, name end
    if name:find('WBP_Commu_Text_C', 1, true) and
        (short == 'text_01' or short == 'text_02') then return true, name end
    if name:find('WBP_Commu_NovelText_C', 1, true) and
        (short == 'text_word' or short == 'text_word_dlc') then return true, name end
    if name:find('WBP_Commu_Select_C', 1, true) and short:match('^font_text_0[1-4]$') then return true, name end
    return false, name
end

local function discover()
    for _, class_name in ipairs({'RichTextBlock', 'TextBlock'}) do
        for _, object in ipairs(FindAllOf(class_name) or {}) do
            if object:IsValid() and not Ruby.is_generated(object) then
                local selected, name = is_dialogue_source(object)
                if selected then
                    local address = object:GetAddress()
                    local entry = entries[address]
                    if not entry or entry.name ~= name then
                        if entry and entry.renderer then entry.renderer:detach() end
                        entries[address] = {source = object, name = name, class_name = class_name, notes = {}}
                        log('Discovered ' .. name)
                    end
                end
            end
        end
    end
    discovered = true
end

local function once(entry, key, message)
    if not entry.notes[key] then entry.notes[key] = true; log(message .. ': ' .. entry.name) end
end

local function options_for(entry)
    local cinema = entry.name:find('WBP_Commu_Cinema_C', 1, true) ~= nil
    return {
        min_base_size = 18,
        gap = 0,
        line_gap = 0,
        max_vertical_slack = entry.name:find('WBP_Commu_Message_C', 1, true) and 4 or 0,
        fallback_style = {
            font_asset = '/Game/Widget/Font/FONT-JP.FONT-JP', face = 'Text',
            size = cinema and 30 or 29,
            color = cinema and {0.945098, 0.945098, 0.945098, 1} or {0.033105, 0.033105, 0.033105, 1},
            outline_size = cinema and 0 or 3,
            outline_color = cinema and {0.879623, 0.879623, 0.879623, 0.8} or {0.828125, 0.828125, 0.828125, 0.5},
        },
    }
end

local function inspect(entry)
    local text = entry.source:GetText():ToString()
    local changed = text ~= entry.last_text
    if changed then
        -- Remove the previous line before waiting for the native reveal to finish.
        if entry.renderer and entry.applied then entry.renderer:hide(); entry.applied = false end
        entry.last_attempt_key, entry.stable_samples = nil, 0
    else
        entry.stable_samples = (entry.stable_samples or 0) + 1
    end
    if entry.last_text and changed then
        if text ~= '' and entry.last_text ~= '' and
            (text:sub(1, #entry.last_text) == entry.last_text or entry.last_text:sub(1, #text) == text) then
            once(entry, 'prefix_observed', 'Native typewriter text observed')
        else
            once(entry, 'whole_replacement', 'Observed whole-text replacement')
        end
    end
    if changed then entry.segments = Lookup.get(database, text) end
    entry.last_text = text
    local segments = entry.segments
    if segments then once(entry, 'exact_match', 'Exact original dialogue matched') end
    local has_reading = false
    for _, segment in ipairs(segments or {}) do
        if segment.reading and segment.reading ~= '' then has_reading = true; break end
    end
    if not enabled or not has_reading or entry.stable_samples < 1 then
        if entry.renderer and entry.applied then entry.renderer:hide(); entry.applied = false end
        entry.last_attempt_key = nil
        return
    end
    if not entry.renderer then
        if entry.attach_failed then return end
        local ok, result = pcall(Ruby.attach, entry.source, options_for(entry))
        if not ok then
            entry.attach_failed = true
            once(entry, 'attach_failed', 'Ruby attach unavailable: ' .. tostring(result))
            return
        end
        entry.renderer = result
        once(entry, 'attached', 'Ruby canvas attached')
    end
    local geometry = entry.renderer:geometry_key()
    local key = text .. '\0' .. tostring(geometry)
    if key ~= entry.last_attempt_key then
        entry.last_attempt_key = key
        local ok, rendered, detail = pcall(entry.renderer.update, entry.renderer, segments, utf8.len(text))
        if not ok then
            entry.renderer:hide()
            entry.applied = false
            once(entry, 'render_error', 'Ruby render failed: ' .. tostring(rendered))
        elseif rendered then
            entry.applied_key, entry.applied = key, true
            once(entry, 'rendered', 'Ruby rendered after the native text stabilized; ' ..
                (detail.fit_summary or 'layout fitted'))
        else
            entry.applied = false
            once(entry, 'render_refused:' .. tostring(detail), 'Ruby not applied: ' .. tostring(detail))
        end
    end
end

local function tick()
    iteration = iteration + 1
    if not discovered or iteration % 8 == 0 then discover() end
    for address, entry in pairs(entries) do
        if not entry.source:IsValid() then
            if entry.renderer then entry.renderer:detach() end
            entries[address] = nil
        else
            local ok, error_message = pcall(inspect, entry)
            if not ok then
                if entry.renderer then entry.renderer:hide(); entry.applied = false end
                once(entry, 'inspect_error', 'Source inspection failed: ' .. tostring(error_message))
            end
        end
    end
end

RegisterKeyBind(Key.F7, function()
    ExecuteInGameThread(function()
        enabled = not enabled
        for _, entry in pairs(entries) do
            entry.last_attempt_key, entry.attach_failed = nil, false
            if not enabled then
                if entry.renderer then
                    entry.renderer:detach()
                    entry.renderer, entry.applied = nil, false
                end
            end
        end
        log(enabled and 'Furigana enabled.' or 'Furigana disabled. Original text restored.')
    end)
end)

LoopAsync(250, function()
    if not queued then
        queued = true
        ExecuteInGameThread(function()
            local ok, error_message = pcall(tick)
            queued = false
            if not ok then log('Discovery paused by an error: ' .. tostring(error_message)); discovered = false end
        end)
    end
    return false
end)

log('Furigana enabled. Readings appear after an exact source line remains stable for 250 ms. F7 toggles furigana.')
