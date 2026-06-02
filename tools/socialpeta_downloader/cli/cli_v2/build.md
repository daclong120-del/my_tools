# Quy trình Đóng Gói (Build) CLI V2 (SocialPeta Downloader)

Tài liệu này tài liệu hóa quá trình phân tích hệ thống và hướng dẫn chi tiết cách biên dịch, đóng gói mã nguồn Python của phiên bản CLI V2 thành một thư mục chạy độc lập (`standalone` chứa tệp `.exe` trên Windows) sử dụng phương pháp **Nuitka**.

---

### 1. Phân tích Cấu trúc Dự án & File Cấu hình
Để chuẩn bị cho quá trình đóng gói, chúng tôi đã rà soát cấu trúc thư mục của dự án và các tệp tin liên quan:
* **Môi trường ảo**: Dự án sử dụng Python 3.13 với môi trường ảo tại thư mục `.venv`.
* **Thư mục mã nguồn core**: Các module lõi của ứng dụng nằm tại `tools/socialpeta_downloader`. Do đó, biến môi trường `PYTHONPATH` cần phải được trỏ về thư mục `tools` để Nuitka nhận diện chính xác package `socialpeta_downloader`.
* **Tài nguyên FFmpeg / FFprobe**: Các file thực thi `ffmpeg.exe` và `ffprobe.exe` được lưu trữ tại `electron/resources/` của dự án.
* **Cấu hình đường dẫn trong mã nguồn**: Trong tệp `tools/socialpeta_downloader/config.py`, đường dẫn đến FFmpeg/FFprobe khi ứng dụng chạy ở trạng thái đóng gói (frozen) được định nghĩa là tìm trực tiếp trong thư mục chứa file thực thi (`os.path.dirname(sys.executable)`).

---

### 2. Quy trình Build Chung & Tối Ưu Hóa Tránh Lỗi Biên Dịch

Biên dịch các thư viện lớn như `yt-dlp` (đặc biệt là tệp tự động sinh `lazy_extractors.c` có dung lượng lên tới **71 Megabytes**) rất dễ làm tràn bộ nhớ của trình biên dịch C++ (Lỗi `fatal error C1002: compiler is out of heap space in pass 2` của MSVC). 

Để giải quyết triệt để lỗi này, quy trình đóng gói được tối ưu hóa như sau:

1. **Thiết lập bảng mã và đường dẫn**:
   * Thiết lập biến môi trường `PYTHONPATH=tools`.
   * Cấu hình bảng mã UTF-8 cho Python.
2. **Kích hoạt trình biên dịch C++ 64-bit Native của MSVC**:
   * Sử dụng tập lệnh `vcvarsall.bat amd64` của Visual Studio để đưa trình biên dịch `cl.exe` 64-bit vào môi trường (thay vì dùng bản 32-bit bị giới hạn 2GB bộ nhớ ảo).
3. **Sử dụng cờ `--low-memory` của Nuitka**:
   * Kích hoạt chế độ tiết kiệm bộ nhớ để Nuitka điều phối Scons biên dịch một cách tối ưu, tránh làm nghẽn RAM hệ thống.
4. **Đóng gói Tkinter / Tcl**:
   * Sử dụng cờ `--enable-plugin=tk-inter` để Nuitka tự động đóng gói runtime Tcl/Tk đầy đủ, giải quyết lỗi thiếu tệp `init.tcl` trên máy người dùng.

---

### 3. Tập Lệnh Biên Dịch Nuitka Standalone

Để biên dịch CLI V2, hãy mở cửa sổ dòng lệnh **Command Prompt (CMD)** tại thư mục gốc của dự án `d:\Python\my_tools` và chạy chuỗi lệnh sau.

> [!IMPORTANT]
> Các lệnh này chứa từ khóa `set` và `call` chuyên dụng cho **Command Prompt (CMD)**. Nếu bạn dùng **PowerShell**, vui lòng gõ `cmd` để chuyển sang cửa sổ CMD trước khi dán các lệnh này vào chạy.

```cmd
:: 1. Thiết lập PYTHONPATH trỏ tới thư mục chứa package core
set PYTHONPATH=tools

:: 2. Khởi tạo môi trường compiler x64 Native của MSVC
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64


:: 3. Chạy lệnh biên dịch Nuitka Standalone với chế độ Low Memory
.venv\Scripts\python.exe -m nuitka --standalone --enable-plugin=tk-inter --playwright-include-browser=none --include-package-data=pyfiglet --include-package=socialpeta_downloader --low-memory --output-dir=build/cli tools\socialpeta_downloader\cli\cli_v2\cli.py
```

#### Giải thích các cờ cấu hình Nuitka quan trọng:
* `--standalone`: Tạo bản phân phối chạy độc lập, chứa đầy đủ tệp tin DLL và Python runtime.
* `--enable-plugin=tk-inter`: Tự động nhúng thư viện Tkinter và cấu hình Tcl/Tk để hiển thị hộp thoại chọn thư mục.
* `--playwright-include-browser=none`: Tránh đóng gói/tải các trình duyệt của Playwright (Chromium/Firefox) vì CLI V2 kết nối trực tiếp đến trình duyệt Chrome đang chạy của người dùng qua Remote Debugging (cổng 9222). Điều này giảm đáng kể dung lượng bộ cài và thời gian biên dịch.
* `--include-package-data=pyfiglet`: Nhúng các font chữ ASCII nghệ thuật của thư viện `pyfiglet`.
* `--include-package=socialpeta_downloader`: Đảm bảo đóng gói đầy đủ mã nguồn trong gói core.

* `--low-memory`: Giảm tải tài nguyên và tối ưu hóa bộ nhớ cho trình biên dịch C++.
* `--output-dir=build/cli`: Lưu kết quả biên dịch vào thư mục đích.

---

### 4. Hoàn Thiện Bản Phân Phối (Deployment Steps)

Sau khi quá trình biên dịch Nuitka hoàn tất thành công, thư mục đầu ra sẽ nằm tại:
`d:\Python\my_tools\build\cli\cli.dist`

Để ứng dụng có thể chạy hoàn chỉnh trên các máy tính khác, bạn cần sao chép các tệp nhị phân FFmpeg/FFprobe vào đúng vị trí:

1. **Sao chép FFmpeg/FFprobe trực tiếp vào thư mục gốc của bản phân phối** (bên cạnh `cli.exe` để khớp với logic tìm kiếm của `config.py`):
   ```powershell
   Copy-Item -Path "electron\resources\ffmpeg.exe" -Destination "build\cli\cli.dist\ffmpeg.exe" -Force
   Copy-Item -Path "electron\resources\ffprobe.exe" -Destination "build\cli\cli.dist\ffprobe.exe" -Force
   ```

2. **Sao chép FFmpeg/FFprobe vào thư mục `resources\bin` của bản phân phối** (để dự phòng và đồng bộ cấu trúc):
   ```powershell
   New-Item -ItemType Directory -Force -Path "build\cli\cli.dist\resources\bin"
   Copy-Item -Path "electron\resources\ffmpeg.exe" -Destination "build\cli\cli.dist\resources\bin\ffmpeg.exe" -Force
   Copy-Item -Path "electron\resources\ffprobe.exe" -Destination "build\cli\cli.dist\resources\bin\ffprobe.exe" -Force
   ```

### Cách triển khai và chạy:
1. Nén toàn bộ thư mục `build/cli/cli.dist` thành định dạng `.zip`.
2. Chuyển sang máy tính đích khác.
3. Giải nén và chạy trực tiếp file `cli.exe` bên trong thư mục giải nén để sử dụng ngay mà không cần cài đặt thêm bất kỳ phần mềm nào khác.
