# Exile Delta build + run script (keep this file ASCII-only: Windows PowerShell 5.1)
#   1) kill running ExileDelta.exe
#   2) build mod data (if missing) and icon
#   3) PyInstaller -> dist\ExileDelta.exe
#   4) launch the new exe
#   -Name X : output exe name (default ExileDelta), -Zip : also make dist\X.zip
#   after a successful build, older dist\ExileDelta*.exe / ExileSieve*.exe / .zip are stopped and deleted
param([switch]$NoRun, [switch]$RefreshData, [string]$Name = 'ExileDelta', [switch]$Zip)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$name = $Name
$work = Join-Path $env:TEMP 'exiledelta_build'
$exe = Join-Path $root "dist\$name.exe"

Write-Host "[1/4] stop running $name"
$deadline = (Get-Date).AddSeconds(20)
while (Test-Path $exe) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host ("      killing PID " + (($procs | ForEach-Object { $_.Id }) -join ', '))
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        $procs | Wait-Process -Timeout 5 -ErrorAction SilentlyContinue
    }
    try {
        Remove-Item $exe -Force -ErrorAction Stop
    } catch {
        if ((Get-Date) -gt $deadline) { throw "cannot remove $exe (still running or locked)" }
        Start-Sleep -Milliseconds 500
    }
}

Write-Host "[2/4] data / icon"
if ($RefreshData -or -not (Test-Path "$root\data\mods_ko.json")) {
    if ($RefreshData) { python "$root\tools\build_data.py" --refresh } else { python "$root\tools\build_data.py" }
    if ($LASTEXITCODE -ne 0) { throw 'data build failed' }
}
if ($RefreshData -or -not (Test-Path "$root\data\names_ko.json") -or -not (Test-Path "$root\data\ko_en.json")) {
    if ($RefreshData) { python "$root\tools\build_names.py" --refresh } else { python "$root\tools\build_names.py" }
    if ($LASTEXITCODE -ne 0) { throw 'names build failed' }
}
python "$root\tools\make_icon.py"
if ($LASTEXITCODE -ne 0) { throw 'icon build failed' }

Write-Host "[3/4] PyInstaller"
python -m PyInstaller --noconfirm --onefile --windowed --log-level WARN `
    --name $name `
    --icon "$root\assets\icon.ico" `
    --add-data "$root\data\mods_ko.json;data" `
    --add-data "$root\data\names_ko.json;data" `
    --add-data "$root\data\ko_en.json;data" `
    --add-data "$root\app\pob\headless.lua;pob" `
    --hidden-import paths `
    --hidden-import lupa.luajit21 `
    --exclude-module lupa.lua51 --exclude-module lupa.lua52 --exclude-module lupa.lua53 `
    --exclude-module lupa.lua54 --exclude-module lupa.luajit20 `
    --paths "$root\app" `
    --workpath $work --specpath $work --distpath "$root\dist" `
    "$root\app\main.py"
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

if ($Zip) {
    $zipPath = Join-Path $root "dist\$name.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $exe -DestinationPath $zipPath
    Write-Host "      zip: $zipPath"
}

# remove older builds (other dist\ExileDelta*.exe, old-name ExileSieve*.exe / .zip): stop them if running, then delete
Get-ChildItem (Join-Path $root 'dist') -File -ErrorAction SilentlyContinue |
    Where-Object { ($_.Name -like 'ExileDelta*' -or $_.Name -like 'ExileSieve*') -and ($_.Extension -eq '.exe' -or $_.Extension -eq '.zip') -and $_.BaseName -ne $name } |
    ForEach-Object {
        $old = $_
        if ($old.Extension -eq '.exe') {
            $procs = Get-Process -Name $old.BaseName -ErrorAction SilentlyContinue
            if ($procs) {
                Write-Host ("      stop old " + $old.BaseName + " (PID " + (($procs | ForEach-Object { $_.Id }) -join ', ') + ")")
                $procs | Stop-Process -Force -ErrorAction SilentlyContinue
                $procs | Wait-Process -Timeout 5 -ErrorAction SilentlyContinue
            }
        }
        $removed = $false
        for ($i = 0; $i -lt 10 -and -not $removed; $i++) {
            try { Remove-Item $old.FullName -Force -ErrorAction Stop; $removed = $true }
            catch { Start-Sleep -Milliseconds 500 }
        }
        if ($removed) { Write-Host ("      removed old " + $old.Name) }
        else { Write-Host ("      WARNING: could not remove " + $old.Name + " (in use on another PC?)") }
    }

if (-not $NoRun) {
    Write-Host "[4/4] launch $exe"
    # Smart App Control may block a freshly written unsigned exe for a few seconds -> retry
    $started = $false
    for ($i = 1; $i -le 8 -and -not $started; $i++) {
        try {
            Start-Process -FilePath $exe -ErrorAction Stop
            $started = $true
        } catch {
            Write-Host "      launch blocked (try $i/8), retrying..."
            Start-Sleep -Seconds 2
        }
    }
    if (-not $started) { throw "launch failed: $exe" }
} else {
    Write-Host "[4/4] launch skipped (-NoRun)"
}
