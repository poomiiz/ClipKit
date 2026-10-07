"""Manual ClipKit controls; all host starts/stops are mocked."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient


def main():
    os.environ["CLIPKIT_MANAGED_WINDOW"] = "1"  # former launchers cannot revive automatic shutdown
    from app import app
    app.state.server = SimpleNamespace(should_exit=False)
    app.state.exit_requested = False
    with patch("window_lifecycle.launch_control") as launch, TestClient(app, base_url="http://127.0.0.1:8770") as client:
        assert client.get("/api/window/status").json() == {"managed": False, "windows": 0}
        assert '"managed": false' in client.get("/api/window/watch?session_id=old").text
        assert not app.state.server.should_exit
        for origin in ("http://localhost:8765", "http://127.0.0.1:8765", "http://127.0.0.1:8770"):
            headers = {"origin": origin}
            health = client.get("/api/window/health", headers=headers)
            assert health.status_code == 200 and health.json()["managed"] is False
            assert health.json()["instance"] == os.getpid()
            for action in ("restart", "shutdown"):
                result = client.post("/api/window/" + action, headers=headers)
                assert result.status_code == 202 and result.json()["instance"] == os.getpid()
                launch.assert_called_with(action, 8770)
                if origin.endswith(":8765"):
                    assert result.headers["access-control-allow-origin"] == origin
                    assert client.post("/api/window/exit?instance=" + str(os.getpid()), headers=headers).status_code == 403
                    assert client.post("/api/kit/setup", headers=headers).status_code == 403
        launch.reset_mock()
        for origin in ("null", "https://untrusted.example", "http://localhost:8766"):
            for action in ("restart", "shutdown"):
                assert client.post("/api/window/" + action, headers={"origin": origin}).status_code == 403
        launch.assert_not_called()
        with patch("window_lifecycle.launch_control", side_effect=OSError("not available")):
            assert client.post("/api/window/restart").status_code == 503
        assert client.post("/api/window/exit?instance=0").status_code == 409
        assert not app.state.server.should_exit
        assert client.post("/api/window/exit?instance=" + str(os.getpid())).status_code == 202
        assert app.state.server.should_exit
        assert client.get("/api/window/health").json()["ready"] is False
    app.state.exit_requested = False
    app.state.server.should_exit = False
    helper_check()
    print("ok manual controls: legacy flag, explicit actions, graceful exit, CORS, ownership, helper order")


def helper_check():
    command = r'''
    . $env:CLIPKIT_CONTROL_TEST
    $owner = [pscustomobject]@{ProcessId=4201; ParentProcessId=100; CreationDate=[datetime]'2026-10-07';
        ExecutablePath='C:\Python\python.exe'; CommandLine=('"C:\Python\python.exe" "' + $clipkitAppScript + '"')}
    Assert-ClipKitOwned $owner
    foreach ($badCommand in ('"C:\Python\python.exe" app.py', '"C:\Python\python.exe" "C:\Other\app.py"')) {
        $foreign = $owner | Select-Object *; $foreign.CommandLine = $badCommand
        $rejected = $false
        try { Assert-ClipKitOwned $foreign } catch { $rejected = $true }
        if (-not $rejected) { throw 'Foreign or relative app command was accepted.' }
    }
    $replacement = $owner | Select-Object *; $replacement.CreationDate = $owner.CreationDate.AddSeconds(1)
    $rejected = $false
    try { Assert-ClipKitSame $owner $replacement } catch { $rejected = $true }
    if (-not $rejected) { throw 'Reused PID was accepted.' }
    function Get-CimInstance {
        return @([pscustomobject]@{ProcessId=4202; ParentProcessId=4201},
                 [pscustomobject]@{ProcessId=4203; ParentProcessId=4202},
                 [pscustomobject]@{ProcessId=$PID; ParentProcessId=4201},
                 [pscustomobject]@{ProcessId=4204; ParentProcessId=$PID})
    }
    $children = @(Get-ClipKitChildren $owner)
    if (($children.ProcessId -join ',') -ne '4203,4202') { throw 'Controller subtree was not excluded.' }

    $script:fakeOwner = $null; $script:events = @()
    function Get-ClipKitPortOwner { return $script:fakeOwner }
    function Get-ClipKitProcess { param($ProcessId); if ($script:fakeOwner -and $ProcessId -eq 4201) { return $script:fakeOwner } }
    function Get-ClipKitChildren { param($Owner); return @([pscustomobject]@{ProcessId=4202}) }
    function Invoke-RestMethod { $script:events += 'exit'; $script:fakeOwner = $null }
    function Stop-ClipKitVerified { param($Snapshot); $script:events += ('stop:' + $Snapshot.ProcessId) }
    function Start-ClipKitServer {
        if ($script:fakeOwner) { throw 'Start ran before the old owner released its port.' }
        $script:events += 'start'; return 6001
    }
    function Wait-ClipKitReady { param($ProcessId); $script:events += 'ready'; return $ProcessId }
    $result = Invoke-ClipKitControl 'start'
    if ($result.instance -ne 6001 -or ($script:events -join ',') -ne 'start') { throw 'Start failed.' }
    $script:fakeOwner = $owner; $script:events = @()
    $result = Invoke-ClipKitControl 'restart'
    if ($result.instance -ne 6001 -or ($script:events -join ',') -ne 'exit,stop:4202,start') { throw 'Restart order failed.' }
    $script:fakeOwner = $owner; $script:events = @()
    $result = Invoke-ClipKitControl 'shutdown'
    if ($null -ne $result.instance -or ($script:events -join ',') -ne 'exit,stop:4202') { throw 'Shutdown started another server.' }
    $script:fakeOwner = $owner; $script:events = @()
    $result = Invoke-ClipKitControl 'start'
    if ($result.instance -ne 4201 -or ($script:events -join ',') -ne 'ready') { throw 'Existing owner was duplicated.' }
    $script:fakeOwner = $foreign; $script:events = @()
    $rejected = $false
    try { Invoke-ClipKitControl 'restart' | Out-Null } catch { $rejected = $true }
    if (-not $rejected -or $script:events.Count) { throw 'Foreign owner received control actions.' }
    $script:fakeOwner = $owner; $ExpectedPid = 4200
    $rejected = $false
    try { Invoke-ClipKitControl 'shutdown' | Out-Null } catch { $rejected = $true }
    if (-not $rejected -or $script:events.Count) { throw 'Stale instance received control actions.' }
    Write-Output 'ok shared host helper (all processes mocked)'
    '''
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            env={**os.environ, "CLIPKIT_CONTROL_TEST": str(Path(__file__).resolve().parents[1] / "app" / "control.ps1")},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    main()
