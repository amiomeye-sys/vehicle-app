@echo off
cd /d %~dp0
start cmd /k "python app.py"
start cmd /k "ngrok http 5000"