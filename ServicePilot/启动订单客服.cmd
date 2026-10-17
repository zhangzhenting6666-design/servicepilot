@echo off
chcp 65001 >nul
title ServicePilot Mock Order Customer Service
"%~dp0..\openai-agents-python-main\.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\run_order_customer_service.py" %*
echo.
pause
