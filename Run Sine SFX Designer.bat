@echo off
setlocal
cd /d "%~dp0"
python -c "import numpy" 2>nul
if errorlevel 1 (
    echo NumPy is required for high-quality SFX rendering.
    echo Run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)
python sine_sfx_designer.py
if errorlevel 1 (
    echo.
    echo The SFX Designer could not start. Install Python 3 and ensure it is available as "python".
    pause
)
