@echo off
setlocal
cd /d "%~dp0"
python sine_sfx_designer.py
if errorlevel 1 (
    echo.
    echo The SFX Designer could not start. Install Python 3 and ensure it is available as "python".
    pause
)
