-- Finish only the native logo flow. The game's later startup checks stay native.
local M = {}
local seen = {}
function M.tick(enabled)
    if not enabled then return end
    for _, state in ipairs(FindAllOf('BP_TitleStateLogo_C') or {}) do
        if state:IsValid() and state:GetFullName():find(':PersistentLevel.', 1, true) and state.Phase <= 2 then
            local logo = state.WBP_Logo
            if logo and logo:IsValid() then logo:SetRenderOpacity(0) end
            if logo and logo:IsValid() then
                for _ = 1, 16 do
                    if logo:IsEndFlow() then break end
                    logo:SetNextFlow()
                end
                if logo:IsEndFlow() and not seen[logo:GetAddress()] then
                    seen[logo:GetAddress()] = true
                    print('[StarlitFurigana] Startup logos skipped.\n')
                end
            end
        end
    end
end
return M
