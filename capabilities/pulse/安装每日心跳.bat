@echo off
chcp 65001 >nul
schtasks /Create /TN "incubator_pulse" /TR "D:\SoftWare\User\Vs\xhs\capabilities\pulse\run_heartbeat.bat" /SC DAILY /ST 08:30 /F
if %errorlevel%==0 (
  echo.
  echo [OK] 每日心跳已注册：每天 08:30 自动向微信推晨报
) else (
  echo.
  echo [FAIL] 注册失败，请右键以管理员身份运行重试
)
echo.
pause
