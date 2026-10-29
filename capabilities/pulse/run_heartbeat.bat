@echo off
setlocal
rem Synchronous pulse runner. The Python entrypoint emits safe diagnostic codes.
if not defined PYTHON_EXE set "PYTHON_EXE=python"
set "PYTHONUTF8=1"
rem A preview must not create logs, state, journals, or locks.
for %%A in (%*) do if /i "%%~A"=="--dry-run" goto preview
set "LOG_DIR=%~dp0..\..\.cache\pulse"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%LOG_DIR%" exit /b 1
"%PYTHON_EXE%" -B "%~dp0heartbeat.py" %* >>"%LOG_DIR%\pulse.log" 2>&1
set "PULSE_EXIT=%errorlevel%"
exit /b %PULSE_EXIT%
:preview
"%PYTHON_EXE%" -B "%~dp0heartbeat.py" %*
exit /b %errorlevel%
