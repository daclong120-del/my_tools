@echo off
title Khoi Dong Dev Mode - SocialPeta Downloader
chcp 65001 > nul
echo ===================================================
echo   KHỞI ĐỘNG HỆ THỐNG SOCIALPETA DOWNLOADER (DEV)
echo ===================================================
echo.

:: 1. Khoi dong Backend FastAPI
echo [*] Dang khoi dong Backend API (Port 8003)...
set PYTHONPATH=tools
start "FastAPI Backend (Port 8003)" cmd /k ".venv\Scripts\python -m uvicorn socialpeta_downloader.api:app --host 127.0.0.1 --port 8003"

:: 2. Khoi dong Next.js Dev Server
echo [*] Dang khoi dong Next.js Frontend (Port 3000)...
cd frontends\socialpeta_downloader
start "Next.js Frontend (Port 3000)" cmd /k "npm run dev"
cd ..\..

:: 3. Cho Next.js khoi dong va bat Electron
echo [*] Dang cho 5 giay de Frontend khoi dong...
timeout /t 5 /nobreak > nul

echo [*] Dang mo ung dung Electron...
cd electron
start "Electron App" cmd /c "npm start"
cd ..

echo.
echo [OK] Da khoi dong xong tat ca cac thanh phan!
echo - Backend chay tai: http://127.0.0.1:8003
echo - Frontend chay tai: http://localhost:3000
echo.
echo Ban co the de nguyen cac cua so dong lenh de theo doi log.
pause
