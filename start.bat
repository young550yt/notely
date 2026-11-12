@echo off
rem Start Notely in the background (no console window) and open it.
start "" "C:\Users\young\AppData\Local\Programs\Python\Python312\pythonw.exe" "%~dp0bridge.py"
timeout /t 1 >nul
start "" "http://127.0.0.1:8565/"
