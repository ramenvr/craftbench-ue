<#
.SYNOPSIS
  Own the UE editor lifecycle for CraftBench asset-authoring, so a human does not
  have to open/close it by hand between authoring and grading.

.DESCRIPTION
  CraftBench asset authoring and CraftBench GRADING cannot overlap:

    * authoring  needs a live editor + the Aura MCP bridge
    * grading    needs the editor GONE, because an editor holding UE's Live Coding
                 lock makes every UBT build fail exit 6 in ~13 s

  The Aura MCP tools already cover the happy path -- launch_unreal_project starts a
  marker-recorded headless instance, and shutdown_headless stops it gracefully. But
  shutdown_headless DELIBERATELY refuses to touch an editor a human opened
  (no -AuraHeadless marker), so an attended editor has to be closed some other way.
  That is the gap this script fills.

  Prefer the MCP tools when the instance is MCP-managed. Use `down` here only for an
  attended editor, or when the bridge is unreachable.

.PARAMETER Action
  status  - report editor processes + whether the Live Coding build lock is held
  down    - close every UnrealEditor + LiveCodingConsole process (graceful, then force)
  wait-free - block until the Live Coding lock is free (use before a grade)

.EXAMPLE
  powershell -NoProfile -File tools/scripts/editor_lifecycle.ps1 status
  powershell -NoProfile -File tools/scripts/editor_lifecycle.ps1 down
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('status', 'down', 'wait-free')]
    [string]$Action = 'status',

    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'

# LiveCodingConsole is the process that actually holds UE's build lock; the editor
# spawns it. Killing the editor alone can leave the console (and the lock) behind.
$EditorNames = @('UnrealEditor', 'UnrealEditor-Cmd')
$LockNames = @('LiveCodingConsole')

function Get-Procs {
    param([string[]]$Names)
    Get-Process -Name $Names -ErrorAction SilentlyContinue
}

function Show-Status {
    $editors = Get-Procs -Names $EditorNames
    $locks = Get-Procs -Names $LockNames

    if ($editors) {
        foreach ($p in $editors) {
            $mb = [int]($p.WorkingSet64 / 1MB)
            Write-Output ("EDITOR  {0} pid={1} {2}MB" -f $p.Name, $p.Id, $mb)
        }
    }
    else {
        Write-Output 'EDITOR  none'
    }

    if ($locks) {
        foreach ($p in $locks) {
            Write-Output ("LOCK    {0} pid={1}  <-- holds UE build lock; UBT will FAIL exit 6" -f $p.Name, $p.Id)
        }
        Write-Output 'BUILD   BLOCKED'
    }
    else {
        Write-Output 'BUILD   free'
    }
}

function Stop-All {
    $targets = @(Get-Procs -Names $EditorNames) + @(Get-Procs -Names $LockNames)
    $targets = $targets | Where-Object { $_ }
    if (-not $targets) {
        Write-Output 'nothing to close'
        return
    }

    foreach ($p in $targets) {
        Write-Output ("closing {0} pid={1}" -f $p.Name, $p.Id)
        # CloseMainWindow is the graceful path for an attended editor; a headless one
        # has no window, so fall through to Kill below.
        try { [void]$p.CloseMainWindow() } catch { }
    }

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $left = @(Get-Procs -Names ($EditorNames + $LockNames)) | Where-Object { $_ }
        if (-not $left) { Write-Output 'closed gracefully'; return }
    }

    foreach ($p in (@(Get-Procs -Names ($EditorNames + $LockNames)) | Where-Object { $_ })) {
        Write-Output ("force-killing {0} pid={1}" -f $p.Name, $p.Id)
        try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch { Write-Output ("  kill failed: {0}" -f $_.Exception.Message) }
    }
    Write-Output 'closed'
}

function Wait-Free {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $locks = Get-Procs -Names $LockNames
        $editors = Get-Procs -Names $EditorNames
        if (-not $locks -and -not $editors) {
            Write-Output 'BUILD free'
            return
        }
        Start-Sleep -Seconds 2
    }
    Write-Output 'TIMEOUT: build lock still held'
    exit 1
}

switch ($Action) {
    'status' { Show-Status }
    'down' { Stop-All; Write-Output '---'; Show-Status }
    'wait-free' { Wait-Free }
}
