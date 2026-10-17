@echo off
chcp 65001 >nul
title ServicePilot C02 Live Acceptance
"%~dp0..\openai-agents-python-main\.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\run_order_customer_service.py" --acceptance --fresh-key %*
echo.
pause
