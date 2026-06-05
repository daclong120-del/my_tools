---
name: nuitka-inno-setup-workflow
description: Quy trình tự động hóa đóng gói ứng dụng Python CLI/GUI bằng Nuitka, tạo Launcher C++ ẩn file rác, và build Installer (Setup.exe) bằng Inno Setup.
---

# Kỹ năng: Đóng gói Nuitka + Inno Setup (Cấu trúc "Sạch")

Kỹ năng này mô tả quy trình để đóng gói một ứng dụng Python (CLI hoặc GUI) sao cho nó có kết quả đẹp, chuyên nghiệp, tự động tạo ra file Setup (Installer) chuẩn xác như Electron mà không gặp lỗi quyền ghi file.

## 1. Vấn đề thường gặp khi build Nuitka

1. **Rác thư mục:** Nuitka `--standalone` sinh ra hàng trăm file `.dll`, `.pyd`. Người dùng nhìn vào sẽ thấy rất rối.
2. **Thiếu Launcher .exe đẹp:** Cách thông thường hay dùng `.bat` làm file chạy, trông không chuyên nghiệp và không có icon.
3. **Lỗi Quyền Admin (UAC):** Nếu đóng gói Inno Setup cài vào `C:\Program Files`, app sẽ không thể ghi log hoặc tải data vào thư mục cài đặt trừ khi người dùng chạy bằng quyền Admin.
4. **Tốc độ:** Chạy `--onefile` mỗi lần mở app phải chờ xả nén lâu (2-4 giây).

## 2. Giải pháp Cấu trúc "App Core"

Chúng ta sẽ giải quyết tất cả bằng cấu trúc sau sau khi Nuitka chạy xong:

```text
build\app_dist\
  ├── app_core\               (Thư mục chứa mọi file rác của Nuitka và file .exe thực sự)
  ├── data\                   (Thư mục trống để app ghi data - tuỳ chọn)
  └── MyApp.exe               (File C++ Launcher siêu nhỏ 50KB, CÓ ICON. Chạy file này sẽ gọi file trong app_core)
```

Sau đó, nén toàn bộ `build\app_dist\` thành **MyApp Setup 1.0.0.exe** bằng Inno Setup.

## 3. Tích hợp Launcher C++ & Inno Setup vào Batch Script

Thêm đoạn mã sau vào cuối file `.bat` build Nuitka của bạn (sau khi Nuitka đã build xong):

```bat
@echo off
set "DIST_DIR=build\app_dist"
set "APP_CORE=%DIST_DIR%\app_core"

:: [Bước 1] Chuyển toàn bộ file của Nuitka vào app_core
mkdir "%APP_CORE%"
move "%DIST_DIR%\*" "%APP_CORE%\" > nul 2>&1

:: [Bước 2] Tạo file C++ Launcher & Gắn Icon
copy /Y "path\to\favicon.ico" "%DIST_DIR%\app.ico" > nul
(
echo #include ^<process.h^>
echo #include ^<stdio.h^>
echo #include ^<windows.h^>
echo int main(int argc, char *argv[]) {
echo     char exePath[MAX_PATH];
echo     GetModuleFileNameA(NULL, exePath, MAX_PATH);
echo     char *lastSlash = strrchr(exePath, '\\');
echo     if (lastSlash) *lastSlash = '\0';
echo     char targetExe[MAX_PATH];
echo     snprintf(targetExe, MAX_PATH, "%%s\\app_core\\RealMyApp.exe", exePath);
echo     argv[0] = targetExe;
echo     intptr_t ret = _spawnvp(_P_WAIT, targetExe, argv);
echo     return (int)ret;
echo }
) > "%DIST_DIR%\launcher.c"

echo 1 ICON "app.ico" > "%DIST_DIR%\app.rc"

:: Biên dịch Launcher bằng MSVC (cần gọi vcvarsall.bat trước đó)
pushd "%DIST_DIR%"
rc.exe /nologo app.rc
cl.exe /nologo /O2 /MT launcher.c app.res user32.lib /FeMyApp.exe > nul
del launcher.c app.rc app.res launcher.obj app.ico
popd

:: [Bước 3] Đóng gói Inno Setup
set "INNO_SETUP=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
if not exist "%INNO_SETUP%" set "INNO_SETUP=C:\Program Files (x86)\Inno Setup 6\iscc.exe"

if exist "%INNO_SETUP%" (
    "%INNO_SETUP%" /dMyOutputDir="build" /dMyDistDir="%DIST_DIR%" "scripts\setup_installer.iss"
) else (
    echo [!] Khong tim thay Inno Setup.
)
```

## 4. Cấu hình Inno Setup (.iss)

Tạo file `scripts\setup_installer.iss` với nội dung chú ý ở dòng `DefaultDirName`:

```iss
#define MyAppName "MyApp"
#define MyAppVersion "1.0.0"
#define MyAppExeName "MyApp.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; RẤT QUAN TRỌNG: Cài vào LocalAppData để tránh lỗi quyền ghi file (Permission Denied)
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyAppName} Setup {#MyAppVersion}
SetupIconFile=path\to\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyDistDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
```

## 5. Kết luận

- Mọi logic rác của Python được ẩn đi.
- Tốc độ khởi động siêu tốc (so với `--onefile`).
- Quá trình setup trông như một app Electron thực thụ.
- Không bao giờ bị kẹt lỗi liên quan đến Admin rights khi sinh ra folder hoặc file log tại nơi cài đặt.
