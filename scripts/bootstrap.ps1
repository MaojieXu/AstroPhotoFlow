$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$apfArguments = @($args)
if ($apfArguments -contains '--help') {
    Write-Output 'Windows x64 bootstrap: tools are reused or installed inside .artifacts.'
    Write-Output 'Arguments go to dev_prepare.py; --watch selects dev_frontend.py.'
    Write-Output 'Quickstart: --workspace .artifacts/workspaces/dev --build --start'
    exit 0
}
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This bootstrap supports Windows x64. Other platforms are not validated.'
}
$apfRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $apfRoot
$apfArtifacts = Join-Path $apfRoot '.artifacts'
$apfTools = Join-Path $apfArtifacts 'toolchains'
$apfCache = Join-Path $apfArtifacts 'cache'
if ($env:ASTROPHOTOFLOW_DEV_CACHE) { $apfCache = [IO.Path]::GetFullPath($env:ASTROPHOTOFLOW_DEV_CACHE) }
$env:UV_CACHE_DIR = Join-Path $apfCache 'uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $apfArtifacts 'python'
$env:UV_PYTHON_BIN_DIR = Join-Path $apfArtifacts 'python-bin'
$env:UV_PYTHON_INSTALL_REGISTRY = '0'
$env:LOCALAPPDATA = Join-Path $apfArtifacts 'local-app-data'
$env:APPDATA = Join-Path $apfArtifacts 'app-data'
$env:TEMP = Join-Path $apfArtifacts 'tmp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$apfOffline = $apfArguments -contains '--offline'
if ($apfOffline) { $env:UV_OFFLINE = '1' }
New-Item -ItemType Directory -Force -Path $apfTools, $env:TEMP, $env:LOCALAPPDATA, $env:APPDATA | Out-Null
$apfDevBin = Join-Path $apfArtifacts 'venvs/dev/Scripts'
if (Test-Path -LiteralPath $apfDevBin) { $env:PATH = $apfDevBin + ';' + $env:PATH }

function Find-ApfTool([string]$Name, [string]$Managed, [string]$Version) {
    $apfInstalled = Get-Command $Name -ErrorAction SilentlyContinue
    foreach ($apfCandidate in @($Managed, $apfInstalled.Source)) {
        if (-not $apfCandidate -or -not (Test-Path -LiteralPath $apfCandidate -PathType Leaf)) { continue }
        try {
            $apfVersionLines = @(& $apfCandidate --version 2>$null)
            if ($LASTEXITCODE -ne 0) { continue }
            $apfVersionText = $apfVersionLines[0]
            if ($Name -eq 'node') {
                $apfNodeVersion = [version]$apfVersionText.Trim().TrimStart('v')
                if ($apfNodeVersion -ge [version]'26.8.2' -and $apfNodeVersion -lt [version]'27.0.0') { return $apfCandidate }
            } elseif ($Name -eq 'uv') {
                if ($apfVersionText -match ('^uv ' + [regex]::Escape($Version) + '(\s|$)')) { return $apfCandidate }
            } elseif ($apfVersionText.Trim() -eq $Version) {
                return $apfCandidate
            }
        } catch { Write-Host "Cannot use ${Name}: $($_.Exception.Message)"; continue }
    }
    return $null
}

function Expand-ApfTool([string]$File, [string]$Uri, [string]$Sha256, [string]$Destination) {
    $apfDownloads = Join-Path $apfCache 'toolchains'
    New-Item -ItemType Directory -Force -Path $apfDownloads | Out-Null
    $apfArchive = Join-Path $apfDownloads $File
    if (-not (Test-Path -LiteralPath $apfArchive)) {
        if ($apfOffline) { throw "Offline archive missing: $apfArchive" }
        Write-Host "Downloading $File"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile ($apfArchive + '.pending') -TimeoutSec 120
        if ((Get-FileHash -LiteralPath ($apfArchive + '.pending') -Algorithm SHA256).Hash -ne $Sha256) {
            throw "SHA256 mismatch: $File"
        }
        Move-Item -LiteralPath ($apfArchive + '.pending') -Destination $apfArchive
    }
    if ((Get-FileHash -LiteralPath $apfArchive -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Cached archive SHA256 mismatch: $apfArchive"
    }
    Write-Host "Preparing $File"
    Expand-Archive -LiteralPath $apfArchive -DestinationPath $Destination -Force
}

try {
    $apfUvDirectory = Join-Path $apfTools 'uv'
    $apfUvFiles = @()
    if (Test-Path -LiteralPath $apfUvDirectory) {
        $apfUvFiles = @(Get-ChildItem -LiteralPath $apfUvDirectory -Recurse -Filter uv.exe -File)
    }
    $apfUvManaged = Join-Path $apfUvDirectory 'uv.exe'
    if ($apfUvFiles.Count -eq 1) { $apfUvManaged = $apfUvFiles[0].FullName }
    $apfUv = Find-ApfTool 'uv' $apfUvManaged '0.13.5'
    if (-not $apfUv) {
        Expand-ApfTool 'uv-0.13.5-win-x64.zip' 'https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-pc-windows-msvc.zip' 'a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a' $apfUvDirectory
        $apfUvFiles = @(Get-ChildItem -LiteralPath $apfUvDirectory -Recurse -Filter uv.exe -File)
        if ($apfUvFiles.Count -ne 1) { throw 'UV archive does not contain exactly one uv.exe' }
        $apfUv = Find-ApfTool 'uv' $apfUvFiles[0].FullName '0.13.5'
        if (-not $apfUv) { throw 'Prepared uv version does not match 0.13.5' }
    }
    $env:PATH = (Split-Path -Parent $apfUv) + ';' + $env:PATH
    $apfNodeManaged = Join-Path $apfTools 'node-v26.8.2-win-x64/node.exe'
    $apfNode = Find-ApfTool 'node' $apfNodeManaged ''
    if (-not $apfNode) {
        Expand-ApfTool 'node-v26.8.2-win-x64.zip' 'https://nodejs.org/dist/v26.8.2/node-v26.8.2-win-x64.zip' 'cf02f5d0c06c794b84f277177d5cf3743d0924ca49f6641cd435dd7cb6ee9085' $apfTools
        $apfNode = Find-ApfTool 'node' $apfNodeManaged ''
        if (-not $apfNode) { throw 'Prepared Node version does not satisfy the project requirement' }
    }
    $env:PATH = (Split-Path -Parent $apfNode) + ';' + $env:PATH
    $apfPackage = Get-Content -LiteralPath (Join-Path $apfRoot 'package.json') -Raw | ConvertFrom-Json
    if ($apfPackage.packageManager -notmatch '^pnpm@(\d+\.\d+\.\d+)$') { throw 'packageManager must pin pnpm' }
    $apfPnpmVersion = $Matches[1]
    $apfPnpmDirectory = Join-Path $apfTools 'pnpm'
    $apfPnpmManaged = Join-Path $apfPnpmDirectory 'node_modules/.bin/pnpm.cmd'
    $apfPnpm = Find-ApfTool 'pnpm' $apfPnpmManaged $apfPnpmVersion
    if (-not $apfPnpm) {
        $apfNpm = Join-Path (Split-Path -Parent $apfNode) 'node_modules/npm/bin/npm-cli.js'
        if (-not (Test-Path -LiteralPath $apfNpm)) { throw 'Selected Node has no npm; install the pinned pnpm or use the managed Node archive' }
        Write-Host "Preparing pnpm $apfPnpmVersion"
        $apfNpmArguments = @($apfNpm, 'install', '--prefix', $apfPnpmDirectory, "pnpm@$apfPnpmVersion",
                            '--ignore-scripts', '--no-audit', '--no-fund', '--cache', (Join-Path $apfCache 'npm'))
        if ($apfOffline) { $apfNpmArguments += '--offline' }
        & $apfNode @apfNpmArguments
        if ($LASTEXITCODE -ne 0) { throw "pnpm preparation failed: $LASTEXITCODE" }
        $apfPnpm = Find-ApfTool 'pnpm' $apfPnpmManaged $apfPnpmVersion
        if (-not $apfPnpm) { throw 'Prepared pnpm version does not match packageManager' }
    }
    $env:PATH = (Split-Path -Parent $apfPnpm) + ';' + $env:PATH
    $apfPython = Join-Path $apfArtifacts 'venvs/dev/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $apfPython)) {
        $apfPython = $null
        try {
            $apfPython = (& $apfUv python find --system --no-python-downloads 3.12 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0) { $apfPython = $null }
        } catch { $apfPython = $null }
        if (-not $apfPython) {
            & $apfUv python install --no-registry 3.12.15
            if ($LASTEXITCODE -ne 0) { throw "Python preparation failed: $LASTEXITCODE" }
            $apfPython = (& $apfUv python find --managed-python 3.12.15 | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0) { throw 'Prepared Python cannot be found' }
        }
    }
    $apfEntry = Join-Path $PSScriptRoot 'dev_prepare.py'
    if ($apfArguments -contains '--watch') {
        $apfArguments = @($apfArguments | Where-Object { $_ -ne '--watch' })
        $apfEntry = Join-Path $PSScriptRoot 'dev_frontend.py'
    }
    & $apfPython $apfEntry @apfArguments
    exit $LASTEXITCODE
} catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 1
}
