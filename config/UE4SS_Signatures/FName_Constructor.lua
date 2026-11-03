-- Starlit Season Steam build 8278842, UE 4.24.
-- Identified through KismetStringLibrary.Conv_StringToName's native wrapper.
function Register()
    return '48 89 5C 24 08 57 48 83 EC 30 48 8B D9 48 89 54 24 20 33 C9 41 8B F8 4C 8B DA 44 8B D1 4C 8B'
end

function OnMatchFound(address)
    return address
end
