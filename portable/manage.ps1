param([ValidateSet('Prepare','Uninstall')][string]$Action = 'Prepare')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$gameRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$binRelative = 'StarlitSeason/Binaries/Win64'
$stateRelative = '.starlit-furigana-portable-state'
$patchRelative = 'StarlitSeason/Content/Paks/~mods'
$patchNames = @('pakchunk99-EngPatch.pak','pakchunk99-EngPatch.sig')
$allowed = @("$binRelative/dwmapi.dll", "$binRelative/ue4ss/UE4SS.dll",
    "$binRelative/ue4ss/LICENSE", "$binRelative/ue4ss/UE4SS-settings.ini",
    "$binRelative/ue4ss/Mods/mods.txt")
foreach ($name in @('main.lua','umg_ruby.lua','ruby_layout.lua','reading_lookup.lua','sha256.lua','readings.lua',
    'native_bridge.lua','dialogue_controller.lua','settings.lua','mod_menu.lua','startup.lua','object_registry.lua',
    'ui_annotations.lua','ui_geometry.lua','ui_bindings.lua','backlog.lua','performance_guard.lua',
    'StarlitFuriganaNative.dll','MinHook.LICENSE.txt')) {
    $allowed += "$binRelative/ue4ss/Mods/StarlitFurigana/Scripts/$name"
}
foreach ($name in @('ConsoleManager.lua','FName_Constructor.lua','GameEngineTick.lua')) {
    $allowed += "$binRelative/ue4ss/UE4SS_Signatures/$name"
}

function Inside-Game([string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('\') -or
        $Relative.Contains(':') -or $Relative.Split('/') -contains '..') { throw 'Unsafe package path.' }
    $path = [IO.Path]::GetFullPath((Join-Path $gameRoot $Relative))
    if (-not $path.StartsWith($gameRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Package path leaves the game folder.'
    }
    $cursor = $path
    while ($cursor -ne $gameRoot) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Linked files or folders are not supported: $cursor"
            }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $path
}

function File-Hash([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Remove-EmptyParents($Paths, [string]$Boundary) {
    $directories = @{}
    foreach ($path in $Paths) {
        $cursor = Split-Path -Parent $path
        while ($cursor -eq $Boundary -or $cursor.StartsWith($Boundary + '\', [StringComparison]::OrdinalIgnoreCase)) {
            $directories[$cursor] = $true
            if ($cursor -eq $Boundary) { break }
            $cursor = Split-Path -Parent $cursor
        }
    }
    foreach ($directory in @($directories.Keys | Sort-Object Length -Descending)) {
        try { [IO.Directory]::Delete($directory, $false) } catch [IO.IOException] { }
    }
}

try {
    if (-not (Test-Path -LiteralPath (Inside-Game 'StarlitSeason.exe'))) {
        throw 'Extract the ZIP into the game folder containing StarlitSeason.exe.'
    }
    if (Get-Process -Name 'StarlitSeason','StarlitSeason-Win64-Shipping' -ErrorAction SilentlyContinue) {
        throw 'Close Starlit Season completely before checking or removing the mod.'
    }
    if (Test-Path -LiteralPath (Inside-Game '.starlit-furigana-state')) {
        throw 'An older Python-managed mod is present. Uninstall it before copying this package.'
    }
    $manifest = Get-Content -LiteralPath (Inside-Game 'StarlitFurigana/manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.version -ne 1 -or @($manifest.files).Count -ne $allowed.Count) { throw 'Invalid package manifest.' }
    $seen = @{}
    foreach ($file in $manifest.files) {
        if ($file.path -notin $allowed -or $seen.ContainsKey($file.path) -or $file.sha256 -notmatch '^[a-f0-9]{64}$') {
            throw 'Manifest contains an unowned or duplicate file.'
        }
        $seen[$file.path] = $true
        $path = Inside-Game $file.path
        if (-not (Test-Path -LiteralPath $path)) {
            if ($Action -eq 'Prepare') { throw "Missing package file: $($file.path)" }
        } elseif ((File-Hash $path) -ne $file.sha256) {
            throw "A package file was changed; preserve your edits before proceeding: $($file.path)"
        }
    }
    $statePath = Inside-Game "$stateRelative/state.json"
    $backups = @()
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $backups = @($state.backups)
    }
    $seenBackups = @{}
    foreach ($backup in $backups) {
        $name = [IO.Path]::GetFileName($backup.source)
        if ($name -notin $patchNames -or $backup.source -ne "$patchRelative/$name" -or
            $backup.stored -ne "backups/$name" -or $seenBackups.ContainsKey($name)) { throw 'Invalid patch backup record.' }
        $seenBackups[$name] = $true
        $stored = Inside-Game "$stateRelative/$($backup.stored)"
        if (-not (Test-Path -LiteralPath $stored) -or (File-Hash $stored) -ne $backup.sha256) {
            throw "An English-patch backup is missing or changed: $name"
        }
        if (Test-Path -LiteralPath (Inside-Game $backup.source)) { throw "Patch restore destination is occupied: $name" }
    }

    if ($Action -eq 'Prepare') {
        $shipping = Inside-Game "$binRelative/StarlitSeason-Win64-Shipping.exe"
        if ((File-Hash $shipping) -ne $manifest.shipping_sha256) { throw 'Unsupported game build. This package requires game 1.61 / Steam build 8278842.' }
        $planned = @()
        foreach ($name in $patchNames) {
            $source = Inside-Game "$patchRelative/$name"
            if (Test-Path -LiteralPath $source) {
                $stored = Inside-Game "$stateRelative/backups/$name"
                if (Test-Path -LiteralPath $stored) { throw "Patch backup destination is occupied: $name" }
                $planned += [pscustomobject]@{ source = "$patchRelative/$name"; stored = "backups/$name"; sha256 = (File-Hash $source) }
            }
        }
        $moved = [Collections.Generic.List[object]]::new()
        try {
            foreach ($backup in $planned) {
                $stored = Inside-Game "$stateRelative/$($backup.stored)"
                [IO.Directory]::CreateDirectory((Split-Path -Parent $stored)) | Out-Null
                Move-Item -LiteralPath (Inside-Game $backup.source) -Destination $stored
                $moved.Add($backup)
            }
            if ($planned.Count -gt 0) {
                $data = @{ version = 1; backups = @($backups) + @($planned) } | ConvertTo-Json -Depth 6
                $temporary = Inside-Game "$stateRelative/state.tmp"
                [IO.File]::WriteAllText($temporary, $data, [Text.UTF8Encoding]::new($false))
                Move-Item -LiteralPath $temporary -Destination $statePath -Force
            }
        } catch {
            $failure = $_
            $undo = $moved.ToArray(); [Array]::Reverse($undo)
            foreach ($backup in $undo) {
                Move-Item -LiteralPath (Inside-Game "$stateRelative/$($backup.stored)") -Destination (Inside-Game $backup.source)
            }
            throw $failure
        }
        Write-Output 'Furigana package verified. Launch through Steam; F6 toggles manual/auto, F7 toggles furigana. OPTION has the master switch (F8).'
        Write-Output "Known English-patch files backed up and disabled: $($planned.Count)."
    } else {
        $holdRelative = 'StarlitFurigana/.uninstall-' + [guid]::NewGuid().ToString('N')
        $holdRoot = Inside-Game $holdRelative
        $held = [Collections.Generic.List[object]]::new()
        $restored = [Collections.Generic.List[object]]::new()
        try {
            foreach ($file in $manifest.files) {
                $source = Inside-Game $file.path
                if (Test-Path -LiteralPath $source) {
                    $temporary = Inside-Game "$holdRelative/$($file.path)"
                    [IO.Directory]::CreateDirectory((Split-Path -Parent $temporary)) | Out-Null
                    Move-Item -LiteralPath $source -Destination $temporary
                    $held.Add([pscustomobject]@{ source = $source; temporary = $temporary })
                }
            }
            foreach ($backup in $backups) {
                Move-Item -LiteralPath (Inside-Game "$stateRelative/$($backup.stored)") -Destination (Inside-Game $backup.source)
                $restored.Add($backup)
            }
        } catch {
            $failure = $_
            $undo = $restored.ToArray(); [Array]::Reverse($undo)
            foreach ($backup in $undo) {
                Move-Item -LiteralPath (Inside-Game $backup.source) -Destination (Inside-Game "$stateRelative/$($backup.stored)")
            }
            $undo = $held.ToArray(); [Array]::Reverse($undo)
            foreach ($file in $undo) { Move-Item -LiteralPath $file.temporary -Destination $file.source }
            Remove-EmptyParents @($held.ToArray() | ForEach-Object { $_.temporary }) $holdRoot
            throw $failure
        }
        foreach ($file in $held) { [IO.File]::Delete($file.temporary) }
        Remove-EmptyParents @($held.ToArray() | ForEach-Object { $_.temporary }) $holdRoot
        Remove-EmptyParents @($held.ToArray() | ForEach-Object { $_.source }) (Inside-Game "$binRelative/ue4ss")
        if (Test-Path -LiteralPath $statePath) {
            [IO.File]::Delete($statePath)
            $oldPaths = @($statePath) + @($backups | ForEach-Object { Inside-Game "$stateRelative/$($_.stored)" })
            Remove-EmptyParents $oldPaths (Inside-Game $stateRelative)
        }
        Write-Output "Furigana removed. English-patch files restored: $($restored.Count)."
        Write-Output 'Logs and unrelated files were kept. You may now remove the StarlitFurigana helper folder, the two Furigana CMD files, and README-FURIGANA.txt.'
    }
    exit 0
} catch {
    Write-Output ('Furigana: ' + $_.Exception.Message)
    exit 1
}
