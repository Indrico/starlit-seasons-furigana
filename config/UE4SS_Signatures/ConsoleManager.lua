-- Starlit Season Steam build 8278842: IConsoleManager singleton getter.
-- The alternative default match is a reflected console-variable exec wrapper.
function Register()
    return '48 83 EC 38 48 83 3D ?? ?? ?? ?? 00 0F 85 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 48 89 7C 24 30'
end

function OnMatchFound(address)
    return address
end
