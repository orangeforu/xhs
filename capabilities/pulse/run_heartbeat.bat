@echo off
rem incubator daily pulse (see capabilities/pulse/README.md)
cd /d %~dp0..\..
set NO_PROXY=*
set no_proxy=*
start "" /b "C:\Python314\pythonw.exe" "%~dp0heartbeat.py"
