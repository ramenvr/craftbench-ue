# setup.ps1 — thin wrapper for the CraftBench post-clone setup script.
# Locates a Python (py -3.12 -> py -3 -> python -> python3), then runs the brain
# (tools/scripts/setup_craftbench.py) forwarding all arguments unchanged:
#   .\setup.ps1 [--no-tests] [--json] [--full] [--add-path] [--strict] [--verbose]
# Windows PowerShell 5.1-safe (no &&, no ternary). All logic lives in the brain.

$brain = Join-Path $PSScriptRoot 'tools\scripts\setup_craftbench.py'
if (-not (Test-Path $brain)) {
    Write-Host "FAIL  $brain not found (incomplete clone?)"
    exit 1
}

$candidates = @(
    @{ exe = 'py';      pre = @('-3.12') },
    @{ exe = 'py';      pre = @('-3') },
    @{ exe = 'python';  pre = @() },
    @{ exe = 'python3'; pre = @() }
)

foreach ($c in $candidates) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    & $c.exe $c.pre '--version' *> $null
    if ($LASTEXITCODE -ne 0) { continue }
    & $c.exe $c.pre $brain @args
    exit $LASTEXITCODE
}

Write-Host 'FAIL  no working Python found (need 3.11+; 3.12 preferred). Install it so `py -3.12 --version` works, then re-run.'
exit 1
