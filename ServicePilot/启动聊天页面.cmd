@echo off
chcp 65001 >nul
title ServicePilot Local Chat
"%~dp0..\openai-agents-python-main\.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\run_web.py" %*
echo.
pause
