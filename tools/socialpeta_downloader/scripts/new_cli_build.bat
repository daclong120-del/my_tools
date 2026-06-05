@echo off
title SocialPeta Downloader CLI - Build Script
chcp 65001 > nul

:: Xác định đường dẫn thư mục dự án
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
cd ..\..\..
set "PROJECT_DIR=%CD%"

echo ===================================================
echo [1/6] Thiết lập môi trường biên dịch...
echo ===================================================
set PYTHONPATH=tools
set PYTHONIOENCODING=utf-8

:: Gọi MSVC Compiler x64 để phục vụ biên dịch Launcher C++
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64

:: Dọn dẹp thư mục build cũ nếu có để tránh xung đột file lock
set "RANDVAL=%RANDOM%"
if exist "build\new_cli.dist" (
    ren "build\new_cli.dist" "new_cli.dist.old.%RANDVAL%"
    rd /s /q "build\new_cli.dist.old.%RANDVAL%"
)
if exist "build\SocialPetaDownloaderNew" (
    ren "build\SocialPetaDownloaderNew" "SocialPetaDownloaderNew.old.%RANDVAL%"
    rd /s /q "build\SocialPetaDownloaderNew.old.%RANDVAL%"
)

echo ===================================================
echo [2/6] Bắt đầu biên dịch new_cli.py bằng Nuitka...
echo ===================================================
.venv\Scripts\python.exe -m nuitka --standalone --enable-plugin=tk-inter --playwright-include-browser=none --include-package-data=pyfiglet --include-package=socialpeta_downloader --jobs=10 --nofollow-import-to=yt_dlp.extractor.lazy_extractors --output-dir=build --output-filename=SocialPetaDownloader tools\socialpeta_downloader\scripts\new_cli.py

if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Quá trình biên dịch bằng Nuitka thất bại!
    pause
    exit /b %ERRORLEVEL%
)

echo ===================================================
echo [3/6] Tạo cấu trúc thư mục sạch (App Core)...
echo ===================================================
if not exist "build\new_cli.dist" (
    echo [LOI] Không tìm thấy thư mục build\new_cli.dist sau khi biên dịch!
    pause
    exit /b 1
)

:: Tạo cấu trúc thư mục phân phối
mkdir "build\SocialPetaDownloaderNew"
ren "build\new_cli.dist" "app_core"
move "build\app_core" "build\SocialPetaDownloaderNew\" > nul

set "DIST_DIR=build\SocialPetaDownloaderNew"
set "APP_CORE=%DIST_DIR%\app_core"

echo ===================================================
echo [4/6] Sao chép FFmpeg, FFprobe và thư viện VC++ Runtime...
echo ===================================================
:: Sao chép FFmpeg & FFprobe
copy /Y "electron\resources\ffmpeg.exe" "%APP_CORE%\ffmpeg.exe"
copy /Y "electron\resources\ffprobe.exe" "%APP_CORE%\ffprobe.exe"

:: Sao chép các thư viện DLL của MSVC C++ Redistributable
copy /Y "C:\Windows\System32\msvcp140.dll" "%APP_CORE%\msvcp140.dll"
copy /Y "C:\Windows\System32\msvcp140_1.dll" "%APP_CORE%\msvcp140_1.dll"
copy /Y "C:\Windows\System32\msvcp140_2.dll" "%APP_CORE%\msvcp140_2.dll"
copy /Y "C:\Windows\System32\msvcp140_atomic_wait.dll" "%APP_CORE%\msvcp140_atomic_wait.dll"
copy /Y "C:\Windows\System32\msvcp140_codecvt_ids.dll" "%APP_CORE%\msvcp140_codecvt_ids.dll"
copy /Y "C:\Windows\System32\vcruntime140_threads.dll" "%APP_CORE%\vcruntime140_threads.dll"

echo ===================================================
echo [5/6] Biên dịch C++ Launcher (Ẩn file rác, kèm Icon)...
echo ===================================================
:: Copy icon vào thư mục dist để gán
copy /Y "%PROJECT_DIR%\frontends\socialpeta_downloader\app\favicon.ico" "%DIST_DIR%\app.ico" > nul

:: Tạo mã nguồn C cho Launcher
echo #include ^<process.h^> > "%DIST_DIR%\launcher.c"
echo #include ^<stdio.h^> >> "%DIST_DIR%\launcher.c"
echo #include ^<windows.h^> >> "%DIST_DIR%\launcher.c"
echo int main(int argc, char *argv[]) { >> "%DIST_DIR%\launcher.c"
echo     char exePath[MAX_PATH]; >> "%DIST_DIR%\launcher.c"
echo     GetModuleFileNameA(NULL, exePath, MAX_PATH); >> "%DIST_DIR%\launcher.c"
echo     char *lastSlash = strrchr(exePath, '\\'); >> "%DIST_DIR%\launcher.c"
echo     if (lastSlash) *lastSlash = '\0'; >> "%DIST_DIR%\launcher.c"
echo     char targetExe[MAX_PATH]; >> "%DIST_DIR%\launcher.c"
echo     snprintf(targetExe, MAX_PATH, "%%s\\app_core\\SocialPetaDownloader.exe", exePath); >> "%DIST_DIR%\launcher.c"
echo     argv[0] = targetExe; >> "%DIST_DIR%\launcher.c"
echo     intptr_t ret = _spawnvp(_P_WAIT, targetExe, argv); >> "%DIST_DIR%\launcher.c"
echo     return (int)ret; >> "%DIST_DIR%\launcher.c"
echo } >> "%DIST_DIR%\launcher.c"

:: Tạo file resource
echo 1 ICON "app.ico" > "%DIST_DIR%\app.rc"

:: Biên dịch launcher
pushd "%DIST_DIR%"
rc.exe /nologo app.rc
cl.exe /nologo /O2 /MT launcher.c app.res user32.lib /FeSocialPetaDownloader.exe > nul
:: Dọn dẹp các file trung gian
del launcher.c app.rc app.res launcher.obj app.ico
popd

echo ===================================================
echo [6/6] Tạo file cài đặt Installer bằng Inno Setup...
echo ===================================================
set "INNO_SETUP=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
if not exist "%INNO_SETUP%" set "INNO_SETUP=C:\Program Files (x86)\Inno Setup 6\iscc.exe"

if exist "%INNO_SETUP%" (
    "%INNO_SETUP%" /dMyOutputDir="%PROJECT_DIR%\build" /dMyDistDir="%PROJECT_DIR%\%DIST_DIR%" /dMyProjectDir="%PROJECT_DIR%\" "%PROJECT_DIR%\scripts\setup_installer.iss"
    if not errorlevel 1 (
        echo [OK] Đã tạo thành công bộ cài đặt tại thư mục build\
    ) else (
        echo [LOI] Quá trình tạo bộ cài đặt bằng Inno Setup thất bại.
    )
) else (
    echo [!] Không tìm thấy Inno Setup tại "%INNO_SETUP%". Vui lòng cài đặt bằng:
    echo     winget install -e --id JRSoftware.InnoSetup
)

echo ===================================================
echo HOÀN THÀNH! Bản phân phối sạch đã sẵn sàng tại:
echo %PROJECT_DIR%\%DIST_DIR%
echo ===================================================
pause
