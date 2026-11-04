-- Native line events prepare complete text before its first visible frame.
-- The stability gate remains a fallback when the native bridge is unavailable.
local script = debug.getinfo(1, 'S').source
local directory = script:sub(1, 1) == '@' and script:sub(2):match('^(.*[/\\])') or nil
assert(directory, 'Could not resolve the Furigana script directory')
package.path = directory .. '?.lua;' .. package.path

local Ruby = require('umg_ruby')
local Lookup = require('reading_lookup')
local Settings = require('settings')
local Controller = require('dialogue_controller')
local settings_path = directory .. '../../../../../../../StarlitFurigana/user-settings.ini'
local settings = Settings.load(settings_path)
local bridge, bridge_error = require('native_bridge').load(directory)
local controller = bridge and Controller.new(bridge, settings) or nil
local native_ready = false
local database = dofile(directory .. 'readings.lua')
local entries = {}
local enabled = true
local master_enabled = settings.enabled ~= false
local queued = false
local iteration = 0
local discovered = false
local menu = require('mod_menu').new(settings, function(value) StarlitFuriganaSetEnabled(value) end)
local startup = require('startup')

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
    local ordinary = entry.name:find('WBP_Commu_Message_C', 1, true) ~= nil
    local choice = entry.name:find('WBP_Commu_Select_C', 1, true) ~= nil
    return {
        fixed_size = native_ready,
        fixed_base_size = native_ready and (choice and 22 or cinema and 30 or ordinary and 29 or nil) or nil,
        expand_dialogue = native_ready and ordinary,
        paginate = native_ready and not choice,
        owner = entry.owner,
        prepare_hidden = native_ready,
        min_base_size = 18,
        -- FONT-JP's desired heights include leading above/below the ink.
        -- A negative metric gap brings ruby closer without reducing font size.
        gap = native_ready and -12 or 0,
        line_gap = native_ready and 4 or 0,
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

local function inspect(entry, immediate)
    if not master_enabled then return end
    if native_ready and not entry.native_generation and not entry.choice_ready then return end
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
    if native_ready and text ~= '' and not segments then segments = {{base = text}} end
    if not enabled or (not native_ready and not has_reading) or text == '' or
        (not immediate and not native_ready and entry.stable_samples < 1) then
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
            if controller and entry.native_generation and controller.renderer ~= entry.renderer then
                controller:set_line(entry.renderer, text)
            end
            once(entry, 'rendered', (native_ready and 'Fixed-size ruby rendered; ' or 'Ruby rendered after the native text stabilized; ') ..
                (detail.fit_summary or 'layout fitted'))
        else
            entry.applied = false
            once(entry, 'render_refused:' .. tostring(detail), 'Ruby not applied: ' .. tostring(detail))
        end
    end
end

function StarlitFuriganaNativeReady()
    native_ready = true
    controller:set_manual(settings.manual)
    if not master_enabled then bridge.disable() end
    log('Native dialogue bridge ready. Complete text, fixed fonts; F6 toggles manual/auto, F7 toggles furigana.')
end

function StarlitFuriganaNativeLine(widget_address, generation, expected_text)
    if not master_enabled then return end
    StarlitFuriganaNativeClear()
    controller:set_line(nil, expected_text)
    local owner
    for _, class_name in ipairs({'WidgetCommuScriptMessage', 'WidgetCommuScriptCinema', 'WidgetCommuScriptNovel'}) do
        for _, object in ipairs(FindAllOf(class_name) or {}) do
            if object:IsValid() and object:GetAddress() == widget_address then owner = object; break end
        end
        if owner then break end
    end
    discover()
    if owner then
        for _, field_name in ipairs({'_TextMessage', '_TextMonologue', '_TextBase'}) do
            local ok, source = pcall(function() return owner[field_name] end)
            if ok and source and source:IsValid() and source:GetText():ToString() == expected_text then
                local entry = entries[source:GetAddress()]
                if entry then
                    entry.owner, entry.native_generation, entry.last_attempt_key = owner, generation, nil
                    if entry.renderer and entry.renderer.options then entry.renderer.options.owner = owner end
                    inspect(entry, true)
                    if entry.applied then controller:set_line(entry.renderer, expected_text) end
                    log('Prepared native line ' .. tostring(generation) .. ', characters=' .. tostring(utf8.len(expected_text)) ..
                        ', pages=' .. tostring(entry.renderer and entry.renderer.pages and #entry.renderer.pages or 1))
                    return
                end
            end
        end
    end
    log('Native line retained its original renderer; no matching supported text widget was ready.')
end

function StarlitFuriganaNativeClear()
    if controller then controller:clear() end
    for _, entry in pairs(entries) do
        if entry.native_generation then
            if entry.renderer then entry.renderer:hide() end
            entry.native_generation, entry.applied, entry.last_attempt_key = nil, false, nil
        end
    end
end

function StarlitFuriganaNativeAutoTick(delta)
    if controller then controller:tick(delta) end
end

function StarlitFuriganaConsumeAdvance()
    if not controller then return false end
    local ok, consumed = pcall(controller.advance, controller)
    if not ok then
        log('Pagination unavailable; native advance restored: ' .. tostring(consumed))
        return false
    end
    return consumed
end

function StarlitFuriganaNativeChoices()
    if not master_enabled then return end
    discover()
    for _, entry in pairs(entries) do
        if entry.name:find('WBP_Commu_Select_C', 1, true) then
            entry.last_attempt_key, entry.choice_ready = nil, true
            inspect(entry, true)
        end
    end
end

function StarlitFuriganaSetEnabled(value)
    master_enabled, settings.enabled = value, value
    if not value then
        if bridge then bridge.disable() end
        StarlitFuriganaNativeClear()
        for _, entry in pairs(entries) do
            if entry.renderer then entry.renderer:detach() end
            entry.renderer, entry.applied, entry.last_attempt_key = nil, false, nil
        end
    elseif native_ready then
        controller:set_manual(settings.manual)
        bridge.enable()
    end
    local ok, message = Settings.save(settings_path, settings)
    if not ok then log('Could not save user preferences: ' .. tostring(message)) end
    log(value and 'All mod features enabled.' or 'All mod features disabled. Original game behavior restored.')
end

local function tick()
    iteration = iteration + 1
    menu:tick()
    if native_ready then startup.tick(master_enabled) end
    if not master_enabled then return end
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

if Key.F6 then RegisterKeyBind(Key.F6, function()
    ExecuteInGameThread(function()
        if not master_enabled then log('Enable the mod in Options before changing dialogue mode.'); return end
        if not native_ready then log('Manual/auto control is unavailable without the supported native bridge.'); return end
        controller:set_manual(not controller.manual)
        local ok, message = Settings.save(settings_path, settings)
        if not ok then log('Could not save user preferences: ' .. tostring(message)) end
        log(controller.manual and 'Manual dialogue: press the normal advance input to continue.' or 'Automatic dialogue enabled.')
    end)
end) end

RegisterKeyBind(Key.F7, function()
    ExecuteInGameThread(function()
        if not master_enabled then log('Enable the mod in Options before toggling furigana.'); return end
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
        if controller and controller.text then controller:set_line(nil, controller.text) end
        log(enabled and 'Furigana enabled.' or 'Furigana disabled. Original text restored.')
    end)
end)

if Key.F8 then RegisterKeyBind(Key.F8, function()
    ExecuteInGameThread(function() menu:toggle_visible() end)
end) end

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

if bridge then
    ExecuteWithDelay(1000, function() ExecuteInGameThread(bridge.initialize) end)
else
    log('Native bridge unavailable; using the legacy renderer: ' .. tostring(bridge_error))
end
log('Furigana enabled. F7 toggles furigana.')
