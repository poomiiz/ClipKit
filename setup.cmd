@echo off
rem Double-click once on a new machine: runs scripts\setup.ps1 for the workspace folder you type.
set "WS=%~1"
if "%WS%"=="" set /p "WS=Workspace folder, e.g. D:\EditorKrab: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" -Workspace "%WS%"
pause
