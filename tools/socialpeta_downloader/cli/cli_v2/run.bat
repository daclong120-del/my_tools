@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo  SOCIALPETA DOWNLOADER - KHOI DONG CLI V2
echo ===================================================

REM Di chuyen ve thu muc goc cua du an (di len 4 cap thu muc)
set "BATCH_DIR=%~dp0"
cd /d "%BATCH_DIR%..\..\..\.."

if exist ".venv\Scripts\python.exe" (
    echo [+] Dang su dung Python tu Virtual Environment...
    .venv\Scripts\python.exe tools\socialpeta_downloader\cli\cli_v2\cli.py
) else (
    echo [-] Khong tim thay thu muc .venv. Thu chay bang python mac dinh...
    python tools\socialpeta_downloader\cli\cli_v2\cli.py
)

pause
