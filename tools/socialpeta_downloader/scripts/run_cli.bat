@echo off
title SocialPeta Downloader CLI
chcp 65001 > nul
cd /d "%~dp0"
cd ..\..\..

:: Check if any arguments are passed
if not "%~1"=="" goto RUN_WITH_ARGS

:MENU
cls
echo ===================================================
echo   SOCIALPETA DOWNLOADER UNIFIED CLI TOOL
echo ===================================================
echo.
echo Vui lòng chọn hành động bạn muốn thực hiện:
echo [1] start-chrome  - Khởi động Chrome debug mode (cổng 9222)
echo [2] list-tabs     - Liệt kê các tab SocialPeta đang hoạt động
echo [3] connect-tab   - Kiểm tra kết nối CDP tới tab hiện tại
echo [4] scrape        - Cào dữ liệu từ trang hiện tại lưu vào CSV
echo [5] crawl         - Chạy cào và tải tự động hoàn toàn (Full Flow)
echo [6] clear         - Dọn dẹp phiên tải cũ (SQLite, file tạm)
echo [7] Trợ giúp đầy đủ (help)
echo [8] Thoát
echo.

set choice=
set /p choice="Nhập lựa chọn của bạn (1-8): "

if "%choice%"=="1" goto CMD_START_CHROME
if "%choice%"=="2" goto CMD_LIST_TABS
if "%choice%"=="3" goto CMD_CONNECT_TAB
if "%choice%"=="4" goto CMD_SCRAPE
if "%choice%"=="5" goto CMD_CRAWL
if "%choice%"=="6" goto CMD_CLEAR
if "%choice%"=="7" goto CMD_HELP
if "%choice%"=="8" goto CMD_EXIT

echo.
echo [-] Lựa chọn không hợp lệ. Vui lòng thử lại.
pause
goto MENU

:CMD_START_CHROME
echo.
echo [*] Đang khởi chạy Chrome debug...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py start-chrome
goto END

:CMD_LIST_TABS
echo.
echo [*] Đang quét danh sách các tab...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py list-tabs
goto END

:CMD_CONNECT_TAB
echo.
echo [*] Đang kiểm tra kết nối CDP...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py connect-tab
goto END

:CMD_SCRAPE
echo.
echo [*] Đang tiến hành cào trang hiện tại...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py scrape
goto END

:CMD_CRAWL
echo.
echo [*] Đang khởi chạy Full Flow (Cào + Tải tự động)...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py crawl --pages 10 --threads 5
goto END

:CMD_CLEAR
echo.
echo [*] Đang tiến hành dọn dẹp...
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py clear
goto END

:CMD_HELP
echo.
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py --help
goto END

:CMD_EXIT
exit /b 0

:RUN_WITH_ARGS
.venv\Scripts\python.exe tools/socialpeta_downloader/scripts/new_cli.py %*
exit /b %ERRORLEVEL%

:END
echo.
echo ===================================================
echo Hoàn thành! Nhấn phím bất kỳ để đóng cửa sổ.
pause > nul
