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
local commands = {}
local menu = require('mod_menu').new(settings, function(value) StarlitFuriganaSetEnabled(value) end)
local startup = require('startup')

local function log(message)
    print('[StarlitFurigana] ' .. message .. '\n')
end
local ui = require('ui_annotations').new(database, bridge, require('ui_bindings'), log)
ui:set_enabled(master_enabled and enabled)
local performance_suspended = false
local performance = require('performance_guard').new(function()
    return bridge and bridge.clock and bridge.clock() or os.clock()
end, function(active)
    performance_suspended = active
    ui:set_suspended(active)
    if active then
        if controller then controller:clear() end
        for _, entry in pairs(entries) do
            if entry.renderer then entry.renderer:detach() end
            entry.renderer, entry.applied, entry.last_attempt_key = nil, false, nil
            entry.native_generation, entry.choice_ready = nil, nil
        end
    end
    log(active and 'MV/live: furigana work suspended.' or 'MV/live ended: furigana work resumed.')
end)

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

local Registry = require('object_registry')
local owners = Registry.new({'/Script/imal.WidgetCommuScriptMessage', '/Script/imal.WidgetCommuScriptCinema',
    '/Script/imal.WidgetCommuScriptNovel'})
local sources = Registry.new({'/Script/UMG.RichTextBlock', '/Script/UMG.TextBlock'}, function(object)
    return not Ruby.is_generated(object) and is_dialogue_source(object)
end)

local function register_source(object)
    local address = object:GetAddress()
    local name = object:GetFullName()
    local entry = entries[address]
    if not entry or entry.name ~= name then
        if entry and entry.renderer then entry.renderer:detach() end
        entry = {source = object, name = name, notes = {}}
        entries[address] = entry
    end
    return entry
end

local function discover()
    for _, object in pairs(sources:objects()) do
        register_source(object)
    end
end

local function once(entry, key, message)
    if not entry.notes[key] then
        entry.notes[key] = true
        if key:find('failed', 1, true) or key:find('error', 1, true) or key:find('refused', 1, true) then
            log(message .. ': ' .. entry.name)
        end
    end
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
    if not master_enabled or performance_suspended then return end
    if native_ready and not entry.native_generation and not entry.choice_ready then return end
    -- Native assignment/choice events own the text. Idle ticks only check geometry.
    local text = native_ready and not immediate and entry.last_text or entry.source:GetText():ToString()
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
    if not master_enabled or performance:poll(true) then return end
    StarlitFuriganaNativeClear()
    controller:set_line(nil, expected_text)
    local owner = owners:find(widget_address)
    if owner then
        if owner:IsA('/Script/imal.WidgetCommuScriptMessage') then
            local name = owner._WidgetName
            if name and name:IsValid() then ui:changed(name._TextName, true) end
        end
        for _, field_name in ipairs({'_TextMessage', '_TextMonologue', '_TextBase'}) do
            local ok, source = pcall(function() return owner[field_name] end)
            if ok and source and source:IsValid() and source:GetText():ToString() == expected_text then
                local entry = is_dialogue_source(source) and register_source(source)
                if entry then
                    entry.owner, entry.native_generation, entry.last_attempt_key = owner, generation, nil
                    if entry.renderer and entry.renderer.options then entry.renderer.options.owner = owner end
                    inspect(entry, true)
                    if entry.applied then controller:set_line(entry.renderer, expected_text) end
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
    if controller and not performance_suspended then controller:tick(delta) end
end

function StarlitFuriganaConsumeAdvance()
    if not controller or performance_suspended then return false end
    local ok, consumed = pcall(controller.advance, controller)
    if not ok then
        log('Pagination unavailable; native advance restored: ' .. tostring(consumed))
        return false
    end
    return consumed
end

function StarlitFuriganaNativeChoices()
    if not master_enabled or performance:poll(true) then return end
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
    ui:set_enabled(value and enabled)
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
    local pending = commands
    commands = {}
    for _, callback in ipairs(pending) do callback() end
    if performance:poll() then return end
    menu:tick()
    if native_ready then startup.tick(master_enabled) end
    discover()
    owners:objects()
    for address, entry in pairs(entries) do
        if not entry.source:IsValid() or entry.source:GetFullName() ~= entry.name then
            if entry.renderer then entry.renderer:detach() end
            entries[address] = nil
        elseif master_enabled then
            local ok, error_message = pcall(inspect, entry)
            if not ok then
                if entry.renderer then entry.renderer:hide(); entry.applied = false end
                once(entry, 'inspect_error', 'Source inspection failed: ' .. tostring(error_message))
            end
        end
    end
end

-- Input callbacks only queue work. Never allocate game-thread callback refs
-- from an async/input thread while UE4SS is dispatching another Lua callback.
local function bind(key, callback)
    if key then RegisterKeyBind(key, function() commands[#commands + 1] = callback end) end
end

bind(Key.F6, function()
    if not master_enabled then log('Enable the mod in Options before changing dialogue mode.'); return end
    if not native_ready then log('Manual/auto control is unavailable without the supported native bridge.'); return end
    controller:set_manual(not controller.manual)
    local ok, message = Settings.save(settings_path, settings)
    if not ok then log('Could not save user preferences: ' .. tostring(message)) end
    log(controller.manual and 'Manual dialogue: press the normal advance input to continue.' or 'Automatic dialogue enabled.')
end)

bind(Key.F7, function()
    if not master_enabled then log('Enable the mod in Options before toggling furigana.'); return end
    enabled = not enabled
    ui:set_enabled(enabled)
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

bind(Key.F8, function() menu:toggle_visible() end)

LoopInGameThreadWithDelay(16, function()
    local detected, active = pcall(performance.poll, performance)
    if not detected or active then return end
    local ok, error_message = pcall(ui.tick, ui)
    if not ok then log('UI annotations deferred: ' .. tostring(error_message)) end
end)

LoopInGameThreadWithDelay(250, function()
    local ok, error_message = pcall(tick)
    if not ok then log('Discovery paused by an error: ' .. tostring(error_message)) end
end)

if bridge then
    ExecuteInGameThreadWithDelay(1000, bridge.initialize)
else
    log('Native bridge unavailable; using the legacy renderer: ' .. tostring(bridge_error))
end
log('Furigana enabled. F7 toggles furigana.')
