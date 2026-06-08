@echo off
title SocialPeta Downloader CLI
chcp 65001 > nul
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Tim kiem thu muc chua thu muc ao .venv o phia tren
set "PROJECT_DIR="
set "CURRENT_DIR=%CD%"

:loop
if exist "%CURRENT_DIR%\.venv" (
    set "PROJECT_DIR=%CURRENT_DIR%"
    goto :found
)
set "PREV_DIR=%CURRENT_DIR%"
cd ..
set "CURRENT_DIR=%CD%"
if "%CURRENT_DIR%"=="%PREV_DIR%" goto :not_found
goto :loop

:not_found
echo [LOI] Khong tim thay thu muc goc du an chua .venv!
pause
exit /b 1

:found
:: Quay lai thu muc chua script
cd /d "%SCRIPT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%\tools"

if not "%~1"=="" (
    "%PROJECT_DIR%\.venv\Scripts\python.exe" new_cli.py %*
) else (
    "%PROJECT_DIR%\.venv\Scripts\python.exe" new_cli.py
)

