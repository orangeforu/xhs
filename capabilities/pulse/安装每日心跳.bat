@echo off
setlocal
rem Not run or deployment-verified. No registration without explicit consent.
rem This task is independent of the Friday AI cron.
if /i not "%~1"=="--install" (
  if not "%~1"=="" exit /b 1
  echo This creates a LOCAL daily 08:30 task. It does not configure Friday AI review.
  echo Read README.md and verify the Python environment before installing.
  choice /C NY /N /M "Install incubator_pulse on this PC? [N/Y] "
  if errorlevel 3 exit /b 1
  if not errorlevel 2 exit /b 1
)
rem No /F: do not overwrite an existing task or request elevated privileges.
schtasks /Create /TN "incubator_pulse" /TR "\"%~dp0run_heartbeat.bat\"" /SC DAILY /ST 08:30
set "PULSE_EXIT=%errorlevel%"
if "%PULSE_EXIT%"=="0" (
  echo REGISTRATION_ACCEPTED: Delivery and deployment remain unverified.
) else (
  echo REGISTRATION_FAILED: Check task settings manually.
)
exit /b %PULSE_EXIT%
