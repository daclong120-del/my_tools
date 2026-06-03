# Quy trình Đóng Gói (Build) CLI V2 (SocialPeta Downloader)

Tài liệu này hướng dẫn chi tiết cách biên dịch và đóng gói mã nguồn Python của phiên bản CLI V2 thành duy nhất một tệp thực thi độc lập (**Single `.exe`**) sử dụng phương pháp **Nuitka Onefile**.

---

### 1. Nguyên lý Đóng gói & Tự động Nhúng Tài nguyên
Bản build CLI V2 được thiết kế để phân phối dưới dạng **1 file thực thi duy nhất** (`SocialPetaDownloader.exe`) chạy độc lập trên mọi máy tính Windows mà không cần cài đặt Python hay cài thêm FFmpeg/FFprobe:
* **Tự động nhúng FFmpeg/FFprobe**: Script đóng gói tự động dò tìm vị trí tệp nhị phân `ffmpeg.exe` và `ffprobe.exe` trong hệ thống (`PATH`) và nhúng trực tiếp chúng làm tài nguyên bên trong file `.exe` bằng Nuitka.
* **Tự động giải nén khi chạy**: Khi khởi chạy file `.exe` trên máy khách, Nuitka sẽ tự động giải nén các tệp nhị phân này vào một thư mục tạm thời trong hệ thống. Lõi chương trình (`config.py`) đã được cập nhật để tự động phát hiện thư mục tạm này và gọi FFmpeg/FFprobe trực tiếp từ đó để xử lý video và check trùng lặp (dHash) mà không sinh tệp rác ra ngoài ổ đĩa.
* **Không sinh thư mục rác**: Toàn bộ luồng khởi tạo thư mục mặc định (`data/videos`) đã được loại bỏ khi import config. Thư mục lưu trữ thực tế chỉ được tạo khi tiến trình tải bắt đầu (mặc định lưu tại thư mục `Downloads\SocialPeta_Downloader` của máy khách).

---

### 2. Yêu cầu Môi trường trước khi Build
Trước khi tiến hành biên dịch, hãy đảm bảo máy tính phát triển (dev) của bạn đáp ứng các yêu cầu sau:
1. **Python 3.13** cùng môi trường ảo tại thư mục `.venv` của dự án (đã cài đặt đầy đủ `requirements.txt` và `nuitka`).
2. **FFmpeg & FFprobe** đã được cài đặt và cấu hình đường dẫn trong biến môi trường `PATH` của hệ thống (script build sẽ tự động tìm kiếm qua lệnh `shutil.which`).
3. **C++ Compiler**: Đã cài đặt **Visual Studio 2022** (bản Community/Professional/Enterprise) có tích hợp gói công cụ C++ (MSVC).

---

### 3. Tập Lệnh Biên Dịch Nuitka Onefile

Để biên dịch, hãy mở cửa sổ dòng lệnh **Command Prompt (CMD)** tại thư mục gốc của dự án `d:\Python\my_tools` và thực hiện các bước sau.

> [!IMPORTANT]
> Phải sử dụng **Command Prompt (CMD)** vì các lệnh môi trường C++ (`vcvarsall.bat`) được thiết kế riêng cho CMD. Nếu bạn dùng PowerShell, vui lòng gõ `cmd` để chuyển chế độ trước khi dán lệnh.

```cmd
:: 1. Kích hoạt môi trường compiler x64 Native của MSVC (tránh lỗi tràn bộ nhớ ảo compiler heap space)
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64

:: 2. Chạy script đóng gói tự động bằng Nuitka
.venv\Scripts\python.exe scripts\build_cli_v2_nuitka.py
```

#### Giải thích cơ chế hoạt động của `build_cli_v2_nuitka.py`:
Script sẽ tự động chạy lệnh Nuitka với các tham số tối ưu:
* `--onefile`: Đóng gói toàn bộ chương trình thành một file `.exe` duy nhất.
* `--enable-plugin=tk-inter`: Nhúng runtime Tcl/Tk phục vụ Folder Explorer (`tkinter.filedialog`).
* `--playwright-include-browser=none`: Không đóng gói kèm trình duyệt (sử dụng Chrome có sẵn của máy khách để giảm hàng trăm MB dung lượng file).
* `--include-package-data=pyfiglet`: Nhúng các font chữ ASCII nghệ thuật cho Banner.
* `--include-package=socialpeta_downloader`: Compile toàn bộ package lõi của ứng dụng.
* `--include-data-files=<ffmpeg_path>=ffmpeg.exe`: Nhúng FFmpeg vào trong file `.exe`.
* `--include-data-files=<ffprobe_path>=ffprobe.exe`: Nhúng FFprobe vào trong file `.exe`.
* `--low-memory`: Tối ưu hóa việc tiêu thụ RAM của trình biên dịch C++.

---

### 4. Kết quả & Cách sử dụng Bản Phân Phối
Sau khi quá trình biên dịch hoàn tất thành công, tệp đầu ra sẽ nằm tại:
`d:\Python\my_tools\build\SocialPetaDownloader_CLIv2_nuitka\SocialPetaDownloader.exe`

**Cách phân phối:**
1. Copy duy nhất tệp `SocialPetaDownloader.exe` sang bất kỳ máy tính Windows nào khác để sử dụng.
2. Máy khách chạy trực tiếp file `.exe` để mở giao diện CLI V2.
3. Khi chạy lần đầu, tệp sẽ tự khởi tạo cấu hình lưu mặc định trỏ về thư mục `Downloads` của người dùng đó (ví dụ: `C:\Users\<Tên_User>\Downloads\SocialPeta_Downloader`).
