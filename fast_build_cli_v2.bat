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

:: Avoid Pending Deletion lock on Windows by renaming before deleting
set "RANDVAL=%RANDOM%"

if exist "build\cli.dist" (
    ren "build\cli.dist" "cli.dist.old.%RANDVAL%"
    rd /s /q "build\cli.dist.old.%RANDVAL%"
)
if exist "build\fast_build_cli_V2_socialpetaDownloader" (
    ren "build\fast_build_cli_V2_socialpetaDownloader" "fast_build_cli_V2_socialpetaDownloader.old.%RANDVAL%"
    rd /s /q "build\fast_build_cli_V2_socialpetaDownloader.old.%RANDVAL%"
)

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

:: Tao cau truc thu muc chinh
mkdir "build\fast_build_cli_V2_socialpetaDownloader"
ren "build\cli.dist" "app_core"
move "build\app_core" "build\fast_build_cli_V2_socialpetaDownloader\" > nul

if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the tao cau truc thu muc app_core!
    pause
    exit /b %ERRORLEVEL%
)

set "DIST_DIR=build\fast_build_cli_V2_socialpetaDownloader"
set "APP_CORE=%DIST_DIR%\app_core"

echo ===================================================
echo [4/4] Sao chep FFmpeg, FFprobe va cac thu vien VC++ Runtime...
echo ===================================================

:: Sao chep vao thu muc goc cua dist
copy /Y "electron\resources\ffmpeg.exe" "%APP_CORE%\ffmpeg.exe"
copy /Y "electron\resources\ffprobe.exe" "%APP_CORE%\ffprobe.exe"

:: Sao chep cac file DLL cua MSVC C++ Redistributable tu System32
copy /Y "C:\Windows\System32\msvcp140.dll" "%APP_CORE%\msvcp140.dll"
copy /Y "C:\Windows\System32\msvcp140_1.dll" "%APP_CORE%\msvcp140_1.dll"
copy /Y "C:\Windows\System32\msvcp140_2.dll" "%APP_CORE%\msvcp140_2.dll"
copy /Y "C:\Windows\System32\msvcp140_atomic_wait.dll" "%APP_CORE%\msvcp140_atomic_wait.dll"
copy /Y "C:\Windows\System32\msvcp140_codecvt_ids.dll" "%APP_CORE%\msvcp140_codecvt_ids.dll"
copy /Y "C:\Windows\System32\vcruntime140_threads.dll" "%APP_CORE%\vcruntime140_threads.dll"

:: Khoi tao thu muc data\videos
if not exist "%DIST_DIR%\data\videos" mkdir "%DIST_DIR%\data\videos"

:: Tao file Launcher .exe co icon
echo ===================================================
echo [5/5] Tao Launcher .exe (voi icon goc)...
echo ===================================================

:: Copy icon vao thu muc tam de dung cho rc.exe
copy /Y "%PROJECT_DIR%frontends\socialpeta_downloader\app\favicon.ico" "%DIST_DIR%\app.ico" > nul

:: Tao ma nguon C cho launcher
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

:: Bien dich C thanh EXE
pushd "%DIST_DIR%"
rc.exe /nologo app.rc
cl.exe /nologo /O2 /MT launcher.c app.res user32.lib /FeSocialPetaDownloader.exe > nul
:: Don dep file rac cua C compiler
del launcher.c app.rc app.res launcher.obj app.ico
popd

:: Kiem tra va chay Inno Setup de tao file Setup
set "INNO_SETUP=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
if not exist "%INNO_SETUP%" set "INNO_SETUP=C:\Program Files (x86)\Inno Setup 6\iscc.exe"

if exist "%INNO_SETUP%" (
    echo ===================================================
    echo [6/6] Dang tao file Installer Setup...
    echo ===================================================
    "%INNO_SETUP%" /dMyOutputDir="%PROJECT_DIR%build" /dMyDistDir="%PROJECT_DIR%%DIST_DIR%" /dMyProjectDir="%PROJECT_DIR%" "%PROJECT_DIR%scripts\setup_installer.iss"
    if not errorlevel 1 (
        echo [OK] Da tao thanh cong SocialPetaDownloader Setup 1.0.0.exe tai thu muc build\
    ) else (
        echo [LOI] Qua trinh tao Setup that bai.
    )
) else (
    echo ===================================================
    echo [!] Khong tim thay Inno Setup tai "%INNO_SETUP%"
    echo [!] Vui long cai dat Inno Setup de tu dong tao file Setup.
    echo [!] Lenh cai dat: winget install -e --id JRSoftware.InnoSetup
    echo ===================================================
)

echo ===================================================
echo HOAN THANH! Ban dong goi da san sang tai: %DIST_DIR%
echo Nguoi dung chi can chay file SocialPetaDownloader.bat
echo ===================================================
pause
