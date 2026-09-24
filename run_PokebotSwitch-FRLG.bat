@echo off
setlocal
cd /d "%~dp0"
py run_ui.py
if errorlevel 1 python run_ui.py
if errorlevel 1 pause
