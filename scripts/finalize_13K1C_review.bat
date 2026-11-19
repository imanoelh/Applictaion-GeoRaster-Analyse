@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "PYTHON=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Project Python environment not found: "%PYTHON%"
  exit /b 2
)
"%PYTHON%" "%PROJECT_ROOT%\scripts\finalize_13K1C_review.py"
exit /b %ERRORLEVEL%
