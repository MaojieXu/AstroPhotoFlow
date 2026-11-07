$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$apfArguments = @($args)
if ($apfArguments -contains '--help') {
    Write-Output 'Windows x64 bootstrap: tools are reused or installed inside .artifacts.'
    Write-Output 'Arguments go to dev_prepare.py; --watch selects dev_frontend.py.'
    Write-Output 'Quickstart: --workspace .artifacts/workspaces/dev --build --start'
    exit 0
}
$apfRoot = Split-Path -Parent $PSScriptRoot
$apfArtifacts = Join-Path $apfRoot '.artifacts'
$apfWatch = $apfArguments -contains '--watch'
$apfRunId = [Guid]::NewGuid().ToString('N')
$apfStarted = [DateTimeOffset]::UtcNow
$apfClock = [Diagnostics.Stopwatch]::StartNew()
$apfLogs = Join-Path $apfArtifacts "logs/dev-prepare/$apfRunId"
$apfReceipt = Join-Path $apfArtifacts 'dev-prepare.json'
New-Item -ItemType Directory -Force -Path $apfLogs | Out-Null
$apfStage = [ordered]@{ name = 'bootstrap'; log = (Join-Path $apfLogs 'bootstrap.log'); exit_code = $null }
$apfReport = [ordered]@{ run_id = $apfRunId; started_at = $apfStarted.ToString('o'); arguments = $apfArguments;
    completed = $false; ready = $false; stages = @($apfStage) }
$apfExitCode = 1
$apfTranscript = $false

function Write-ApfReceipt {
    if ($apfWatch) { return }
    $apfJson = $apfReport | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText(($apfReceipt + '.pending'), $apfJson, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath ($apfReceipt + '.pending') -Destination $apfReceipt -Force
}

try {
Write-ApfReceipt
Start-Transcript -LiteralPath $apfStage.log | Out-Null
$apfTranscript = $true
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This bootstrap supports Windows x64. Other platforms are not validated.'
}
Set-Location -LiteralPath $apfRoot
$apfTools = Join-Path $apfArtifacts 'toolchains'
$apfCache = Join-Path $apfArtifacts 'cache'
if (-not $env:ASTROPHOTOFLOW_DEV_CACHE -and (Test-Path -LiteralPath (Join-Path $apfRoot '.git') -PathType Leaf)) {
    $apfGitPointer = (Get-Content -LiteralPath (Join-Path $apfRoot '.git') -Raw).Trim()
    if (-not $apfGitPointer.StartsWith('gitdir: ')) { throw 'Invalid worktree Git pointer' }
    $apfGitTarget = $apfGitPointer.Substring(8)
    if (-not [IO.Path]::IsPathRooted($apfGitTarget)) { $apfGitTarget = Join-Path $apfRoot $apfGitTarget }
    $apfGitDir = [IO.Path]::GetFullPath($apfGitTarget)
    $apfCommonFile = Join-Path $apfGitDir 'commondir'
    if (Test-Path -LiteralPath $apfCommonFile -PathType Leaf) {
        $apfCommonDir = [IO.Path]::GetFullPath((Join-Path $apfGitDir (Get-Content -LiteralPath $apfCommonFile -Raw).Trim()))
        if ((Split-Path -Leaf $apfCommonDir) -eq '.git') {
            $apfCache = Join-Path (Split-Path -Parent $apfCommonDir) '.artifacts/cache'
        }
    }
}
if ($env:ASTROPHOTOFLOW_DEV_CACHE) { $apfCache = [IO.Path]::GetFullPath($env:ASTROPHOTOFLOW_DEV_CACHE) }
for ($apfIndex = 0; $apfIndex -lt $apfArguments.Count; $apfIndex++) {
    if ($apfArguments[$apfIndex] -eq '--cache-dir') {
        if ($apfIndex + 1 -ge $apfArguments.Count -or $apfArguments[$apfIndex + 1].StartsWith('--')) {
            throw '--cache-dir requires a directory'
        }
        $apfCache = [IO.Path]::GetFullPath($apfArguments[++$apfIndex])
    } elseif ($apfArguments[$apfIndex].StartsWith('--cache-dir=')) {
        $apfCacheValue = $apfArguments[$apfIndex].Substring('--cache-dir='.Length)
        if (-not $apfCacheValue) { throw '--cache-dir requires a directory' }
        $apfCache = [IO.Path]::GetFullPath($apfCacheValue)
    }
}
$env:ASTROPHOTOFLOW_DEV_CACHE = $apfCache
$apfReport['cache_dir'] = $apfCache
Write-ApfReceipt
foreach ($apfCacheCheck in @($apfCache, (Join-Path $apfCache 'npm/_logs'))) {
    try {
        New-Item -ItemType Directory -Force -Path $apfCacheCheck | Out-Null
        $apfProbe = Join-Path $apfCacheCheck ('.apf-write-check-' + $apfRunId)
        $apfStream = [IO.FileStream]::new($apfProbe, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
            [IO.FileShare]::None, 1, [IO.FileOptions]::DeleteOnClose)
        $apfStream.Dispose()
    } catch {
        throw "Cache is not writable: $apfCacheCheck. Check execution permissions or select a writable --cache-dir. $($_.Exception.Message)"
    }
}
$env:UV_CACHE_DIR = Join-Path $apfCache 'uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $apfArtifacts 'managed-python'
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
        if ($apfOffline) { $apfNpmArguments += '--offline' } else { $apfNpmArguments += '--prefer-offline' }
        & $apfNode @apfNpmArguments
        if ($LASTEXITCODE -ne 0) { throw "pnpm preparation failed: $LASTEXITCODE" }
        $apfPnpm = Find-ApfTool 'pnpm' $apfPnpmManaged $apfPnpmVersion
        if (-not $apfPnpm) { throw 'Prepared pnpm version does not match packageManager' }
    }
    $env:PATH = (Split-Path -Parent $apfPnpm) + ';' + $env:PATH
    $apfPythonVersion = '3.12.15'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    & $apfUv python install --no-registry $apfPythonVersion
    if ($LASTEXITCODE -ne 0) { throw "Python preparation failed: $LASTEXITCODE" }
    $apfBasePython = (& $apfUv python find $apfPythonVersion | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or -not $apfBasePython -or -not (Test-Path -LiteralPath $apfBasePython)) {
        throw "Managed Python $apfPythonVersion cannot be found"
    }
    $apfVenvDirectory = Join-Path $apfArtifacts 'venvs/dev'
    $apfPython = Join-Path $apfVenvDirectory 'Scripts/python.exe'
    if (Test-Path -LiteralPath $apfPython) {
        $apfVenvHome = $null
        $apfVenvConfig = Join-Path $apfVenvDirectory 'pyvenv.cfg'
        if (Test-Path -LiteralPath $apfVenvConfig) {
            $apfHomeLine = Get-Content -LiteralPath $apfVenvConfig | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
            if ($apfHomeLine) { $apfVenvHome = ($apfHomeLine -replace '^home\s*=\s*', '').Trim() }
        }
        $apfVenvMatches = $false
        if ($apfVenvHome -and (Test-Path -LiteralPath $apfVenvHome)) {
            try {
                $apfVenvMatches = ((Resolve-Path -LiteralPath $apfVenvHome).Path -eq (Resolve-Path -LiteralPath (Split-Path -Parent $apfBasePython)).Path)
            } catch { $apfVenvMatches = $false }
        }
        if (-not $apfVenvMatches) {
            $apfVenvPython = Join-Path $apfVenvDirectory 'Scripts/python.exe'
            try {
                $apfVenvLock = [System.IO.File]::Open($apfVenvPython, 'Open', 'ReadWrite', 'None')
                $apfVenvLock.Close()
            } catch {
                throw "Cannot recreate the development venv: $apfVenvPython is in use. Stop the workspace services or any other process using that venv, then retry."
            }
            Write-Host 'Recreating development venv for managed Python 3.12.15'
            Remove-Item -LiteralPath $apfVenvDirectory -Recurse -Force
            $apfPython = $apfBasePython
        }
    } else {
        $apfPython = $apfBasePython
    }
    $env:ASTROPHOTOFLOW_DEV_PYTHON = $apfBasePython
    $apfEntry = Join-Path $PSScriptRoot 'dev_prepare.py'
    if ($apfArguments -contains '--watch') {
        $apfArguments = @($apfArguments | Where-Object { $_ -ne '--watch' })
        $apfEntry = Join-Path $PSScriptRoot 'dev_frontend.py'
    }
    $apfStage['elapsed_seconds'] = [Math]::Round($apfClock.Elapsed.TotalSeconds, 3)
    $apfStage['exit_code'] = 0
    Write-ApfReceipt
    if (-not $apfWatch) { $env:ASTROPHOTOFLOW_DEV_PREPARE_RUN_ID = $apfRunId }
    & $apfPython $apfEntry @apfArguments
    $apfExitCode = $LASTEXITCODE
    if (-not $apfWatch) {
        $apfChildReport = Get-Content -LiteralPath $apfReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($apfChildReport.run_id -ne $apfRunId -or -not $apfChildReport.finished_at) {
            throw 'Preparation did not return a receipt for this invocation'
        }
        $apfReport = [ordered]@{}
        foreach ($apfProperty in $apfChildReport.PSObject.Properties) { $apfReport[$apfProperty.Name] = $apfProperty.Value }
        if ($apfExitCode -ne 0) { $apfReport['completed'] = $false }
    }
} catch {
    $apfReport['completed'] = $false
    $apfReport['ready'] = $false
    $apfReport['error'] = $_.Exception.Message
    $apfExitCode = 1
    Write-Error $_.Exception.Message -ErrorAction Continue
} finally {
    if ($null -eq $apfStage.exit_code) {
        $apfStage['exit_code'] = $apfExitCode
        $apfStage['elapsed_seconds'] = [Math]::Round($apfClock.Elapsed.TotalSeconds, 3)
    }
    $apfReport['finished_at'] = [DateTimeOffset]::UtcNow.ToString('o')
    $apfReport['elapsed_seconds'] = [Math]::Round($apfClock.Elapsed.TotalSeconds, 3)
    Write-ApfReceipt
    if ($apfTranscript) { Stop-Transcript | Out-Null }
}
exit $apfExitCode
