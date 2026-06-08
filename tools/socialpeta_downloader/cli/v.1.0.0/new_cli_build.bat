@echo off
title SocialPeta Downloader CLI - Build Script
chcp 65001 > nul

:: Xac dinh duong dan thu muc du an
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Tim kiem thu muc chua thu muc ao .venv o phia tren de xac dinh PROJECT_DIR
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
:: Di chuyen ve thu muc du an de thuc hien build
cd /d "%PROJECT_DIR%"

echo ===================================================
echo [1/6] Thiet lap moi truong bien dich...
echo ===================================================
set "PYTHONPATH=%PROJECT_DIR%\tools"
set PYTHONIOENCODING=utf-8

:: Tim kiem vcvarsall.bat cho MSVC Compiler x64 de phuc vu bien dich Launcher C++
set "VCVARSALL="
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat"
) else if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat"
) else if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat"
) else if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
)

if "%VCVARSALL%"=="" (
    echo [LOI] Khong tim thay vcvarsall.bat de bien dich Launcher C++!
    pause
    exit /b 1
)

:: Xoa bo tat ca dau ngoac kep trong bien PATH va unset VSCODE_NLS_CONFIG de tranh loi cu phap trong vcvarsall.bat
set "PATH=%PATH:"=%"
set "VSCODE_NLS_CONFIG="

call "%VCVARSALL%" amd64

:: Don dep thu muc build cu neu co de tranh xung dot file lock
set "RANDVAL=%RANDOM%"
if exist "build\new_cli.dist" (
    ren "build\new_cli.dist" "new_cli.dist.old.%RANDVAL%"
    rd /s /q "build\new_cli.dist.old.%RANDVAL%"
)
if exist "build\SocialPetaDownloaderNew" (
    ren "build\SocialPetaDownloaderNew" "SocialPetaDownloaderNew.old.%RANDVAL%"
    rd /s /q "build\SocialPetaDownloaderNew.old.%RANDVAL%"
)

:: Mac dinh se giu lai thu muc build cache (new_cli.build) de Nuitka thuc hien bien dich tang dan (incremental build) rat nhanh.
:: Chi xoa khi nguoi dung truyen tham so /clean hoặc -clean
set "CLEAN_BUILD=false"
if "%~1"=="/clean" set "CLEAN_BUILD=true"
if "%~1"=="-clean" set "CLEAN_BUILD=true"

if "%CLEAN_BUILD%"=="true" (
    if exist "build\new_cli.build" (
        echo [*] Dang don dep thu muc cache bien dich - Clean build...
        ren "build\new_cli.build" "new_cli.build.old.%RANDVAL%"
        rd /s /q "build\new_cli.build.old.%RANDVAL%"
    )
)

echo ===================================================
echo [2/6] Bat dau bien dich new_cli.py bang Nuitka...
echo ===================================================
.venv\Scripts\python.exe -m nuitka --standalone --enable-plugin=tk-inter --enable-plugin=anti-bloat --noinclude-pytest-mode=nofollow --noinclude-setuptools-mode=nofollow --playwright-include-browser=none --include-package-data=pyfiglet --include-package=socialpeta_downloader --jobs=10 --nofollow-import-to=yt_dlp.extractor.lazy_extractors --output-dir=build --output-filename=SocialPetaDownloader "%SCRIPT_DIR%new_cli.py"


if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Qua trinh bien dich bang Nuitka that bai!
    pause
    exit /b %ERRORLEVEL%
)

echo ===================================================
echo [3/6] Tao cau truc thu muc sach (App Core)...
echo ===================================================
if not exist "build\new_cli.dist" (
    echo [LOI] Khong tim thay thu muc build\new_cli.dist sau khi bien dich!
    pause
    exit /b 1
)

:: Tao cau truc thu muc phan phoi
mkdir "build\SocialPetaDownloaderNew"
ren "build\new_cli.dist" "app_core"
move "build\app_core" "build\SocialPetaDownloaderNew\" > nul

set "DIST_DIR=build\SocialPetaDownloaderNew"
set "APP_CORE=%DIST_DIR%\app_core"

echo ===================================================
echo [4/6] Sao chep FFmpeg, FFprobe va thu vien VC++ Runtime...
echo ===================================================
:: Sao chep FFmpeg & FFprobe (Uu tien tu resources\bin neu co)
if exist "resources\bin\ffmpeg.exe" (
    copy /Y "resources\bin\ffmpeg.exe" "%APP_CORE%\ffmpeg.exe"
) else (
    copy /Y "electron\resources\ffmpeg.exe" "%APP_CORE%\ffmpeg.exe"
)

if exist "resources\bin\ffprobe.exe" (
    copy /Y "resources\bin\ffprobe.exe" "%APP_CORE%\ffprobe.exe"
) else (
    copy /Y "electron\resources\ffprobe.exe" "%APP_CORE%\ffprobe.exe"
)

:: Sao chep cac thu vien DLL cua MSVC C++ Redistributable de tro giup run standalone
if exist "C:\Windows\System32\vcruntime140.dll" copy /Y "C:\Windows\System32\vcruntime140.dll" "%APP_CORE%\vcruntime140.dll"
copy /Y "C:\Windows\System32\msvcp140.dll" "%APP_CORE%\msvcp140.dll"
copy /Y "C:\Windows\System32\msvcp140_1.dll" "%APP_CORE%\msvcp140_1.dll"
copy /Y "C:\Windows\System32\msvcp140_2.dll" "%APP_CORE%\msvcp140_2.dll"
copy /Y "C:\Windows\System32\msvcp140_atomic_wait.dll" "%APP_CORE%\msvcp140_atomic_wait.dll"
copy /Y "C:\Windows\System32\msvcp140_codecvt_ids.dll" "%APP_CORE%\msvcp140_codecvt_ids.dll"
copy /Y "C:\Windows\System32\vcruntime140_threads.dll" "%APP_CORE%\vcruntime140_threads.dll"

:: Khoi tao thu muc data (tuong thich voi cau truc sach cua build_cli.md)
if not exist "%DIST_DIR%\data" mkdir "%DIST_DIR%\data"
echo ===================================================
echo [5/6] Bien dich C++ Launcher (An file rac, kem Icon)...
echo ===================================================
:: Copy icon vao thu muc dist de gan
copy /Y "%PROJECT_DIR%\frontends\socialpeta_downloader\app\favicon.ico" "%DIST_DIR%\app.ico" > nul

:: Tao ma nguon C cho Launcher
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

:: Tao file resource
echo 1 ICON "app.ico" > "%DIST_DIR%\app.rc"

:: Bien dich launcher
pushd "%DIST_DIR%"
rc.exe /nologo app.rc
cl.exe /nologo /O2 /MT launcher.c app.res user32.lib /FeSocialPetaDownloader.exe > nul
:: Don dep cac file trung gian
del launcher.c app.rc app.res launcher.obj app.ico
popd

echo ===================================================
echo [6/6] Tao file cai dat Installer bang Inno Setup...
echo ===================================================
set "INNO_SETUP=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
if not exist "%INNO_SETUP%" set "INNO_SETUP=C:\Program Files (x86)\Inno Setup 6\iscc.exe"

if exist "%INNO_SETUP%" (
    "%INNO_SETUP%" /dMyOutputDir="%PROJECT_DIR%\build" /dMyDistDir="%PROJECT_DIR%\%DIST_DIR%" /dMyProjectDir="%PROJECT_DIR%\\" "%PROJECT_DIR%\scripts\setup_installer.iss"
    if not errorlevel 1 (
        echo [OK] Da tao thanh cong bo cai dat tai thu muc build\
    ) else (
        echo [LOI] Qua trinh tao bo cai dat bang Inno Setup that bai.
    )
) else (
    echo [!] Khong tim thay Inno Setup tai "%INNO_SETUP%". Vui long cai dat bang:
    echo     winget install -e --id JRSoftware.InnoSetup
)

echo ===================================================
echo HOAN THANH! Ban phan phoi sach da san sang tai:
echo %PROJECT_DIR%\%DIST_DIR%
echo ===================================================
pause
