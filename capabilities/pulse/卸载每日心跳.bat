@echo off
chcp 65001 >nul
schtasks /Delete /TN "incubator_pulse" /F 2>nul
echo.
echo [OK] 每日心跳已停止（journal 历史保留，手动跑 run_heartbeat.bat 随时可用）
echo.
pause
