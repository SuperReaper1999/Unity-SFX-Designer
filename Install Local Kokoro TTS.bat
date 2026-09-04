@echo off
setlocal
set "TOOL_ROOT=%~dp0"
set "PYTHONUSERBASE=%TOOL_ROOT%.local-tts"
set "PIP_CACHE_DIR=%TOOL_ROOT%.installer-cache"
set "TEMP=%TOOL_ROOT%.installer-temp"
set "TMP=%TOOL_ROOT%.installer-temp"
if not exist "%PYTHONUSERBASE%" mkdir "%PYTHONUSERBASE%"
if not exist "%TEMP%" mkdir "%TEMP%"
set "PYTHON=%TOOL_ROOT%.python312\python.exe"
if not exist "%PYTHON%" (
  echo Missing the local Python 3.12 runtime. Run the project setup once before this installer.
  pause
  exit /b 1
)
"%PYTHON%" -m pip install --no-cache-dir --target "%PYTHONUSERBASE%" -r "%TOOL_ROOT%requirements-kokoro.txt"
if errorlevel 1 (
  echo.
  echo Local Kokoro installation failed. Nothing was installed on C: by this script.
  pause
  exit /b 1
)
echo.
echo Kokoro installed beneath %PYTHONUSERBASE%
echo Model files download into %TOOL_ROOT%.kokoro-cache on the first generated line.
pause
