@echo off
title SocialPeta Downloader CLI
chcp 65001 > nul

set PYTHONPATH=%~dp0..\..
"%~dp0..\..\..\.venv\Scripts\python.exe" "%~dp0cli.py" %*

if %errorlevel% neq 0 (
    echo [!] Chuong trinh thoat voi loi ^(Ma loi: %errorlevel%^).
    pause
)
