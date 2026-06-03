@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ===================================================
echo [1/4] Thiet lap moi truong bien dich...
echo ===================================================
set PYTHONPATH=tools
set PYTHONIOENCODING=utf-8

:: Goi MSVC Compiler x64
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64

:: Xoa thu muc build cu de tranh xung dot va loi __constants.h
if exist "build\cli.build" rd /s /q "build\cli.build"
if exist "build\cli.dist" rd /s /q "build\cli.dist"
if exist "build\fast_build_cli_V2_socialpetaDownloader" rd /s /q "build\fast_build_cli_V2_socialpetaDownloader"

echo ===================================================
echo [2/4] Bat dau bien dich bang Nuitka 10 luong (Vui long doi)...
echo ===================================================
.venv\Scripts\python.exe -m nuitka --standalone --enable-plugin=tk-inter --playwright-include-browser=none --include-package-data=pyfiglet --include-package=socialpeta_downloader --jobs=10 --nofollow-import-to=yt_dlp.extractor.lazy_extractors --output-dir=build --output-filename=SocialPetaDownloader tools\socialpeta_downloader\cli\cli_v2\cli.py

if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Qua trinh bien dich bang Nuitka that bai!
    pause
    exit /b %ERRORLEVEL%
)

echo ===================================================
echo [3/4] Doi ten thu muc phan phoi va tao cau truc thu muc...
echo ===================================================
if not exist "build\cli.dist" (
    echo [LOI] Khong tim thay thu muc build\cli.dist sau khi bien dich!
    pause
    exit /b 1
)

:: Doi ten build\cli.dist thanh build\fast_build_cli_V2_socialpetaDownloader
ren "build\cli.dist" "fast_build_cli_V2_socialpetaDownloader"

if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the doi ten thu muc cli.dist thanh fast_build_cli_V2_socialpetaDownloader!
    pause
    exit /b %ERRORLEVEL%
)

set "DIST_DIR=build\fast_build_cli_V2_socialpetaDownloader"

echo ===================================================
echo [4/4] Sao chep FFmpeg, FFprobe va cac thu vien VC++ Runtime...
echo ===================================================

:: Sao chep vao thu muc goc cua dist
copy /Y "electron\resources\ffmpeg.exe" "%DIST_DIR%\ffmpeg.exe"
copy /Y "electron\resources\ffprobe.exe" "%DIST_DIR%\ffprobe.exe"

:: Sao chep cac file DLL cua MSVC C++ Redistributable tu System32 de dam bao chay duoc tren may khong co VC++ Runtime
copy /Y "C:\Windows\System32\msvcp140.dll" "%DIST_DIR%\msvcp140.dll"
copy /Y "C:\Windows\System32\msvcp140_1.dll" "%DIST_DIR%\msvcp140_1.dll"
copy /Y "C:\Windows\System32\msvcp140_2.dll" "%DIST_DIR%\msvcp140_2.dll"
copy /Y "C:\Windows\System32\msvcp140_atomic_wait.dll" "%DIST_DIR%\msvcp140_atomic_wait.dll"
copy /Y "C:\Windows\System32\msvcp140_codecvt_ids.dll" "%DIST_DIR%\msvcp140_codecvt_ids.dll"
copy /Y "C:\Windows\System32\vcruntime140_threads.dll" "%DIST_DIR%\vcruntime140_threads.dll"

:: Sao chep vao resources\bin
if not exist "%DIST_DIR%\resources\bin" mkdir "%DIST_DIR%\resources\bin"
copy /Y "electron\resources\ffmpeg.exe" "%DIST_DIR%\resources\bin\ffmpeg.exe"
copy /Y "electron\resources\ffprobe.exe" "%DIST_DIR%\resources\bin\ffprobe.exe"

:: Khoi tao thu muc data\videos
if not exist "%DIST_DIR%\data\videos" mkdir "%DIST_DIR%\data\videos"

echo ===================================================
echo HOAN THANH! Ban dong goi da san sang tai: %DIST_DIR%
echo ===================================================
pause
