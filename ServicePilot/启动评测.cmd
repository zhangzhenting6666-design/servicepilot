@echo off
chcp 65001 >nul
title ServicePilot Live Evaluation
"%~dp0..\openai-agents-python-main\.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\run_evaluation.py" %*
echo.
pause
