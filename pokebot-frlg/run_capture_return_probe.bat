@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage:
    echo   run_capture_return_probe.bat SWITCH_IP [SPECIES_ID]
    echo.
    echo Example:
    echo   run_capture_return_probe.bat 192.168.1.50 25
    exit /b 1
)
set SPECIES=
if not "%~2"=="" set SPECIES=--species %~2
python capture_return_probe.py %~1 %SPECIES% --json capture_return_probe_trace.json
pause
