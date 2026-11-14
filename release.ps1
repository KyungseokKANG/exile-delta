# Exile Delta release script (keep this file ASCII-only: Windows PowerShell 5.1)
#   powershell -ExecutionPolicy Bypass -File .\release.ps1 -NotesFile notes.md [-Pre]
#   1) read version from app\version.py (tag v<ver> must not exist yet)
#   2) build.ps1 -Name ExileDelta -NoRun  -> dist\ExileDelta.exe, dist\app-<ver>.zip, dist\manifest.json
#   3) dist\ExileDelta-<ver>.zip (exe for first install)
#   4) git commit + tag + push, gh release create (assets: ExileDelta-<ver>.zip, app-<ver>.zip, manifest.json)
#   -Pre : mark as pre-release (apps do NOT auto-update to it; for testing)
param([Parameter(Mandatory = $true)][string]$NotesFile, [switch]$Pre)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
Set-Location $root

$vtext = Get-Content (Join-Path $root 'app\version.py') -Raw
if ($vtext -notmatch 'VERSION\s*=\s*"([^"]+)"') { throw 'VERSION not found in app\version.py' }
$ver = $Matches[1]
$tag = "v$ver"
Write-Host "release $tag"

$existing = git tag --list $tag
if ($existing) { throw "tag $tag already exists - bump VERSION in app\version.py" }
if (-not (Test-Path $NotesFile)) { throw "notes file not found: $NotesFile" }

powershell -ExecutionPolicy Bypass -File (Join-Path $root 'build.ps1') -Name ExileDelta -NoRun
if ($LASTEXITCODE -ne 0) { throw 'build failed' }

$exe = Join-Path $root 'dist\ExileDelta.exe'
$full = Join-Path $root "dist\ExileDelta-$ver.zip"
$app = Join-Path $root "dist\app-$ver.zip"
$man = Join-Path $root 'dist\manifest.json'
foreach ($f in @($exe, $app, $man)) { if (-not (Test-Path $f)) { throw "missing $f" } }
if (Test-Path $full) { Remove-Item $full -Force }
Compress-Archive -Path $exe -DestinationPath $full

gh auth setup-git  # git push uses the gh login
git add -A
$changes = git status --porcelain
if ($changes) { git commit -q -m "Release $tag" }
git tag $tag
git push -q origin HEAD
git push -q origin $tag

$ghArgs = @('release', 'create', $tag, $full, $app, $man, '--title', "Exile Delta $tag", '--notes-file', $NotesFile)
if ($Pre) { $ghArgs += '--prerelease' }
gh @ghArgs
if ($LASTEXITCODE -ne 0) { throw 'gh release create failed' }
Write-Host "done: https://github.com/KyungseokKANG/exile-delta/releases/tag/$tag"
