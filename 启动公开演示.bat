@echo off
cd /d "%~dp0"
echo Starting SoilLens public demo. Please keep this window open...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1"
set "SOILLENS_EXIT=%ERRORLEVEL%"
if not "%SOILLENS_EXIT%"=="0" (
  echo.
  echo Start failed. The error is saved in tmp\demo-server.stderr.log
  echo Please send that log to Codex.
)
if "%SOILLENS_EXIT%"=="0" (
  echo.
  echo The browser is open. Closing this window will not stop the demo.
)
echo.
pause
exit /b %SOILLENS_EXIT%
