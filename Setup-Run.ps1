param(
    [ValidateSet('install','uninstall','check')][string]$Action = 'install',
    [string]$GamePath,
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'titanfall2mod_no_body_no_reload\runtime')
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-VerifiedArchive($Name, $Entry) {
    $archive = Join-Path $RuntimeRoot ($Name + '.zip')
    if ((Test-Path -LiteralPath $archive) -and (Get-FileHash -LiteralPath $archive).Hash -eq $Entry.sha256) { return $archive }
    Write-Host ('Downloading verified runtime: ' + $Name)
    $temporary = $archive + '.download'
    Invoke-WebRequest -Uri $Entry.url -OutFile $temporary -UseBasicParsing -TimeoutSec 60
    if ((Get-FileHash -LiteralPath $temporary).Hash -ne $Entry.sha256) { throw ('Download checksum mismatch: ' + $Name) }
    Move-Item -LiteralPath $temporary -Destination $archive -Force
    return $archive
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
    if (-not $GamePath) { $GamePath = Read-Host 'Titanfall 2 game folder (containing Titanfall2.exe)' }
    $GamePath = $GamePath.Trim().Trim('"')
    if (-not $GamePath) { throw 'No game folder selected.' }
    $GamePath = (Resolve-Path -LiteralPath $GamePath).Path
    if (Get-Process -Name Titanfall2,Titanfall2_trial -ErrorAction SilentlyContinue) { throw 'Close Titanfall 2 completely before installing or restoring.' }
    $config = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'compatibility.json') | ConvertFrom-Json
    if ($Action -ne 'uninstall') {
        $baseManifest = Join-Path $GamePath '.circuitlord-vr-mods\Titanfall2VR.json'
        if (-not (Test-Path -LiteralPath $baseManifest)) { throw 'Install the official CircuitLord Titanfall2VR base mod first.' }
        if ((Get-Content -Raw -LiteralPath $baseManifest | ConvertFrom-Json).version -ne $config.required_mod_version) { throw 'Required BASE MOD: Titanfall2VR 1.0.25. Installer 1.2.12 is a separate version number.' }
        $dll = Join-Path $GamePath 'TF2VR\plugins\Titanfall2VR.dll'
        if (-not (Test-Path -LiteralPath $dll)) { throw 'The base VR DLL was not found.' }
        $hash = (Get-FileHash -LiteralPath $dll).Hash
        if ($hash -notin @($config.dll_original_sha256, $config.dll_patched_sha256)) { throw 'Unsupported VR DLL. Restore the official Titanfall2VR 1.0.25 files first.' }
    }
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    $lock = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'runtime-lock.json') | ConvertFrom-Json
    $pythonRoot = Join-Path $RuntimeRoot 'python-3.12.10'
    $python = Join-Path $pythonRoot 'python.exe'
    if (-not (Test-Path -LiteralPath (Join-Path $pythonRoot '.ready'))) {
        Expand-Archive -LiteralPath (Get-VerifiedArchive 'python-3.12.10' $lock.python) -DestinationPath $pythonRoot -Force
        @('python312.zip','.','Lib/site-packages','import site') | Set-Content -LiteralPath (Join-Path $pythonRoot 'python312._pth') -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $pythonRoot '.ready') -Value $lock.python.sha256 -Encoding ASCII
    }
    $arguments = @((Join-Path $PSScriptRoot 'src\patcher.py'), $Action, '--game', $GamePath)
    if ($Action -eq 'install') {
        $sitePackages = Join-Path $pythonRoot 'Lib\site-packages'
        if (-not (Test-Path -LiteralPath (Join-Path $sitePackages '.numpy-2.3.5-ready'))) {
            Expand-Archive -LiteralPath (Get-VerifiedArchive 'numpy-2.3.5' $lock.numpy) -DestinationPath $sitePackages -Force
            Set-Content -LiteralPath (Join-Path $sitePackages '.numpy-2.3.5-ready') -Value $lock.numpy.sha256 -Encoding ASCII
        }
        $nodeRoot = Join-Path $RuntimeRoot 'node'
        $node = Join-Path $nodeRoot 'node-v22.16.0-win-x64\node.exe'
        if (-not (Test-Path -LiteralPath $node)) { Expand-Archive -LiteralPath (Get-VerifiedArchive 'node-22.16.0' $lock.node) -DestinationPath $nodeRoot -Force }
        $vpkRoot = Join-Path $RuntimeRoot 'tfvpktool-0.3.1'
        if (-not (Test-Path -LiteralPath (Join-Path $vpkRoot 'build\Release\lzham.node'))) { Expand-Archive -LiteralPath (Get-VerifiedArchive 'tfvpktool-0.3.1' $lock.vpk) -DestinationPath $vpkRoot -Force }
        $arguments += @('--node', $node, '--vpk-library', $vpkRoot)
    }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Operation stopped. Read the message above; no unsupported version is patched.' }
    Write-Host 'Done.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
