param(
    [switch]$InstallDependencies,
    [switch]$Initialize,
    [switch]$OfflinePolicies,
    [switch]$CheckOnly,
    [ValidateRange(1024,65535)][int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (-not $InstallDependencies) { throw 'Missing .venv. Run .\start.ps1 -InstallDependencies -Initialize first (Python 3.12 required).' }
    py -3.12 -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python 3.12 environment' }
}
if ($InstallDependencies) {
    & $python -m pip install -r (Join-Path $root 'requirements-lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; existing data was not reset' }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed' }
}
$arguments = @((Join-Path $root 'scripts\start_project.py'), '--port', "$Port")
if ($Initialize) { $arguments += '--initialize' }
if ($OfflinePolicies) { $arguments += '--offline-policies' }
if ($CheckOnly) { $arguments += '--check-only' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Startup checks failed; see the safe error above' }
