param(
    [ValidateSet('start', 'restart', 'shutdown')][string]$Action = 'start',
    [ValidateRange(1, 65535)][int]$Port = 8770,
    [string]$Python = '',
    [int]$ExpectedPid = 0
)
$ErrorActionPreference = 'Stop'
$clipkitAppDir = [IO.Path]::GetFullPath($PSScriptRoot)
$clipkitAppScript = Join-Path $clipkitAppDir 'app.py'

function Get-ClipKitProcess([int]$ProcessId) {
    Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
}

function Get-ClipKitPortOwner {
    $owners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object LocalPort -eq $Port | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -gt 1) { throw "Port $Port has multiple owners; refusing to control it." }
    if ($owners.Count -eq 1) { Get-ClipKitProcess $owners[0] }
}

function Assert-ClipKitOwned($Process) {
    if (-not $Process -or -not $Process.CreationDate -or
        [IO.Path]::GetFileName($Process.ExecutablePath) -notmatch '^python(?:w|[0-9.]*)?\.exe$') {
        throw "Port $Port is not owned by ClipKit Python; refusing to stop it."
    }
    $exe = [regex]::Escape($Process.ExecutablePath)
    $script = [regex]::Escape($clipkitAppScript)
    if ($Process.CommandLine -notmatch "^\s*(?:`"$exe`"|$exe)\s+(?:`"$script`"|$script)\s*$") {
        throw 'ClipKit ownership is ambiguous: expected an absolute app.py command. Refusing to stop it.'
    }
}

function Assert-ClipKitSame($Before, $Current) {
    if ($Current -and ($Before.ProcessId -ne $Current.ProcessId -or
        $Before.CreationDate -ne $Current.CreationDate -or
        $Before.CommandLine -ne $Current.CommandLine -or
        $Before.ParentProcessId -ne $Current.ParentProcessId)) {
        throw "Process identity changed for PID $($Before.ProcessId); refusing to stop a replacement process."
    }
}

function Get-ClipKitChildren($Owner) {
    $all = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $parents = [Collections.Generic.HashSet[int]]::new()
    $null = $parents.Add([int]$Owner.ProcessId)
    $children = @()
    do {
        $added = $false
        foreach ($candidate in $all) {
            # The external controller and its descendants must survive the server.
            if ($candidate.ProcessId -ne $PID -and $parents.Contains([int]$candidate.ParentProcessId) -and
                -not $parents.Contains([int]$candidate.ProcessId)) {
                $null = $parents.Add([int]$candidate.ProcessId)
                $children += $candidate
                $added = $true
            }
        }
    } while ($added)
    [array]::Reverse($children)
    return $children
}

function Stop-ClipKitVerified($Snapshot, [switch]$Descendant) {
    if ($Snapshot.ProcessId -eq $PID) { throw 'Refusing to stop the controller itself.' }
    $current = Get-ClipKitProcess $Snapshot.ProcessId
    if (-not $current) { return }
    try { Assert-ClipKitSame $Snapshot $current }
    catch { if ($Descendant) { return }; throw }
    $native = [Diagnostics.Process]::GetProcessById($Snapshot.ProcessId)
    try {
        $null = $native.Handle # Pin the process handle before the final identity recheck.
        try { Assert-ClipKitSame $Snapshot (Get-ClipKitProcess $Snapshot.ProcessId) }
        catch { if ($Descendant) { return }; throw }
        if ($native.HasExited) { return }
        $native.Kill()
        if (-not $native.WaitForExit(5000)) { throw 'ClipKit process did not stop.' }
    } finally { $native.Dispose() }
}

function Wait-ClipKitReady([int]$ProcessId) {
    $wait = [Diagnostics.Stopwatch]::StartNew()
    while ($wait.Elapsed.TotalSeconds -lt 60) {
        $owner = Get-ClipKitPortOwner
        if ($owner) {
            Assert-ClipKitOwned $owner
            if ($owner.ProcessId -ne $ProcessId) { throw 'Another process took the ClipKit port.' }
            try {
                $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/window/health" -TimeoutSec 2
                if ($health.ready -and $health.instance -eq $ProcessId) { return $ProcessId }
            } catch { Write-Verbose "ClipKit is not ready yet: $_" }
        }
        if (-not (Get-ClipKitProcess $ProcessId)) { throw 'ClipKit could not start. Check video_editor.log.' }
        Start-Sleep -Milliseconds 250
    }
    throw 'ClipKit did not become ready within one minute. Check video_editor.log.'
}

function Start-ClipKitServer {
    $pythonPath = if ($Python) { (Resolve-Path -LiteralPath $Python -ErrorAction Stop).Path }
                  else { (Get-Command python -ErrorAction Stop).Source }
    if (-not [IO.Path]::IsPathRooted($pythonPath)) { throw 'Python must have an absolute executable path.' }
    $env:VIDEO_EDITOR_PORT = "$Port"
    $env:CLIPKIT_MANAGED_WINDOW = '0'
    # Close inherited capture handles so the host worker can receive its result.
    $spawn = @'
import pathlib, subprocess, sys
app = pathlib.Path(sys.argv[1])
with (app.parent / 'video_editor.out.log').open('ab') as out, (app.parent / 'video_editor.log').open('ab') as err:
    server = subprocess.Popen([sys.executable, str(app)], cwd=app.parent, stdin=subprocess.DEVNULL,
                              stdout=out, stderr=err, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
print(server.pid)
'@
    $serverId = & $pythonPath -c $spawn $clipkitAppScript
    if ($LASTEXITCODE -ne 0) { throw 'ClipKit launcher failed.' }
    Wait-ClipKitReady ([int]$serverId)
}

function Invoke-ClipKitControl([string]$Operation) {
    $owner = Get-ClipKitPortOwner
    if ($ExpectedPid -gt 0 -and (-not $owner -or $owner.ProcessId -ne $ExpectedPid)) {
        throw 'ClipKit instance changed before the command ran.'
    }
    if ($owner) { Assert-ClipKitOwned $owner }
    if ($Operation -eq 'start' -and $owner) {
        return @{state = 'succeeded'; instance = (Wait-ClipKitReady $owner.ProcessId)}
    }
    if ($owner) {
        $children = @(Get-ClipKitChildren $owner)
        # Let the original HTTP response finish before asking Uvicorn to exit.
        if ($ExpectedPid -gt 0) { Start-Sleep -Milliseconds 500 }
        Assert-ClipKitSame $owner (Get-ClipKitProcess $owner.ProcessId)
        $portOwner = Get-ClipKitPortOwner
        if ($portOwner -and $portOwner.ProcessId -ne $owner.ProcessId) { throw 'ClipKit port owner changed.' }
        try {
            Invoke-RestMethod -Method Post "http://127.0.0.1:$Port/api/window/exit?instance=$($owner.ProcessId)" -TimeoutSec 2 | Out-Null
        } catch { Write-Verbose "Graceful exit unavailable; verified fallback follows: $_" }
        $wait = [Diagnostics.Stopwatch]::StartNew()
        while ($wait.Elapsed.TotalSeconds -lt 15) {
            $current = Get-ClipKitProcess $owner.ProcessId
            if (-not $current) { break }
            Assert-ClipKitSame $owner $current
            Start-Sleep -Milliseconds 250
        }
        $current = Get-ClipKitProcess $owner.ProcessId
        $portOwner = Get-ClipKitPortOwner
        if ($portOwner -and $portOwner.ProcessId -ne $owner.ProcessId) { throw 'ClipKit port owner changed.' }
        if ($current) {
            Assert-ClipKitOwned $current
            Assert-ClipKitSame $owner $current
            $seen = [Collections.Generic.HashSet[int]]::new()
            $children = @(@(Get-ClipKitChildren $current) + $children |
                Where-Object { $seen.Add([int]$_.ProcessId) })
        }
        foreach ($child in $children) { Stop-ClipKitVerified $child -Descendant }
        if ($current) { Stop-ClipKitVerified $owner }
        $wait.Restart()
        while (Get-ClipKitPortOwner) {
            if ($wait.Elapsed.TotalSeconds -ge 10) { throw 'ClipKit port did not become free; refusing to start another copy.' }
            Start-Sleep -Milliseconds 250
        }
    }
    $instance = if ($Operation -eq 'shutdown') { $null } else { Start-ClipKitServer }
    return @{state = 'succeeded'; instance = $instance}
}

# Dot-sourcing loads the ownership functions for the no-process regression check.
if ($MyInvocation.InvocationName -ne '.') {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $key = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("$clipkitAppScript|$Port"))).Replace('-', '').Substring(0, 16) }
    finally { $sha.Dispose() }
    $mutex = [Threading.Mutex]::new($false, "Local\ClipKitControl-$key")
    $acquired = $false
    try {
        try { $acquired = $mutex.WaitOne(60000) }
        catch [Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Another ClipKit control command is still running.' }
        Invoke-ClipKitControl $Action | ConvertTo-Json -Compress
    } finally {
        if ($acquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}
