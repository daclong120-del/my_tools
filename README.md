# SocialPeta Downloader

> Giải pháp doanh nghiệp tự động hóa tải video quảng cáo hiệu năng cao từ SocialPeta và Quảng Đa Đa (Guangdada).
> Hỗ trợ chạy Web App độc lập hoặc đóng gói ứng dụng Desktop tiện lợi với Electron.

---

## 🌟 Tính Năng Nổi Bật (Features)

- 🚀 **Thu Thập Đa Tab Song Song (Multi-Tab Sniffing)**: Kết nối tới Chrome qua giao thức CDP (Chrome DevTools Protocol) để dò quét dữ liệu trên nhiều tab cùng lúc mà không gây xung đột.
- 📦 **Tải Video Hiệu Năng Cao & Đa Luồng**: Hỗ trợ cơ chế tải tải đa luồng bất đồng bộ với hàng đợi ưu tiên (Priority Queue) và điều khiển băng thông qua Semaphore động.
- 🛡️ **Nhận Diện Trùng Lặp Thông Minh (Deduplication)**:
  - So khớp MD5 hash của file tải về.
  - So khớp độ tương đồng hình ảnh bằng giải thuật `dHash` thông qua `FFmpeg` / `FFprobe`.
  - Cơ chế **dHash Caching** lưu trữ trực tiếp vào JSON metadata giúp giảm tải CPU, tránh việc ffmpeg bị gọi lặp lại.
- 📺 **Trích Xuất Video YouTube**: Tích hợp module xử lý trích xuất trực tiếp liên kết nguồn của các video quảng cáo lưu trữ trên YouTube.
- 🔌 **Hỗ Trợ Multi-Client & Cổng Động (Dynamic Ports)**: Client tự động chỉ định cổng Remote Debugging độc lập thông qua API parameters giúp chạy nhiều phiên bản trình duyệt cùng lúc mà không bị tranh chấp tài nguyên.
- 🛡️ **Bảo Mật SSRF**: Lọc và validate tên miền (`is_safe_url`), chỉ cho phép Playwright điều hướng trong phạm vi an toàn (`socialpeta.com` và `guangdada.com`).
- 📣 **Real-time WebSockets Stream**: Đẩy logs hoạt động và thống kê tiến độ thời gian thực đến giao diện UI của Next.js thông qua mô hình Publisher-Subscriber (Pub-Sub) tin cậy.

---

## 📁 Cấu Trúc Thư Mục Dự Án (Project Structure)

```text
my_tools/
├── .venv/                         # Môi trường ảo Python (Virtual Environment)
├── data/                          # Dữ liệu runtime (được tự động tạo)
│   ├── downloads/                 # Thư mục lưu video tải về thành công
│   └── sessions/                  # Lưu dữ liệu phiên đăng nhập và JSON metadata
├── tools/                         # Các công cụ/backend Python
│   └── socialpeta_downloader/     # Package chính của SocialPeta Downloader
│       ├── api/                   # Các endpoints REST & WebSockets (FastAPI)
│       │   └── routes.py          # Khai báo routes và xử lý request
│       ├── core/                  # Engine cốt lõi (dạng Mixins module)
│       │   ├── chrome.py          # Khởi chạy và kiểm soát Chrome CDP
│       │   ├── deduplication.py   # Tính MD5, dHash và loại bỏ video trùng lặp
│       │   ├── downloader.py      # Tải file từ CDN và quản lý luồng tải
│       │   ├── tab_manager.py     # Quản lý trạng thái và tương tác đa tab
│       │   └── legacy_scraper.py  # Crawl chi tiết ad đơn lẻ hoặc trang tìm kiếm
│       ├── api.py                 # Điểm khởi chạy của FastAPI Server (Port 8003)
│       ├── config.py              # Cấu hình hệ thống (Settings)
│       ├── models.py              # Định nghĩa Pydantic models
│       └── sys_monitor.py         # Giám sát tài nguyên hệ thống (RAM/CPU/Disk)
├── frontends/                     # Giao diện người dùng Next.js
│   └── socialpeta_downloader/     # Mã nguồn Next.js App
├── electron/                      # Ứng dụng Desktop Container (Electron)
│   ├── main.js                    # Luồng chính (Main process) kiểm soát vòng đời app
│   ├── preload.js                 # Bridge kết nối IPC an toàn giữa Web và Native OS
│   └── package.json               # Cấu hình và dependencies của Electron
├── scripts/                       # Scripts tự động hóa build và đóng gói
│   └── build.py                   # Script biên dịch chéo nền tảng (Cross-platform build)
├── run_dev.bat                    # Script chạy nhanh chế độ phát triển trên Windows
├── requirements.txt               # Các thư viện Python phụ thuộc
└── README.md                      # Tài liệu hướng dẫn dự án
```

---

## 💻 Hướng Dẫn Chạy Chế Độ Phát Triển (Dev Mode)

Để phát triển dự án, bạn cần khởi chạy cả Backend API và Frontend.

### Cách 1: Khởi chạy nhanh bằng File Batch (Chỉ áp dụng Windows)
Click đúp chuột vào tệp `run_dev.bat` ở thư mục gốc. Script sẽ tự động:
1. Kích hoạt Backend FastAPI chạy tại `http://127.0.0.1:8003`
2. Khởi chạy Next.js Frontend chạy tại `http://localhost:3000`
3. Khởi chạy Electron App ở chế độ dev trỏ vào frontend.

---

### Cách 2: Khởi chạy thủ công từng phần

#### 1. Khởi động Backend API (Python)
Mở terminal tại thư mục gốc của dự án:
```powershell
# Kích hoạt môi trường ảo
.venv\Scripts\activate

# Đặt PYTHONPATH trỏ vào thư mục tools và chạy API
$env:PYTHONPATH="tools"
python tools/socialpeta_downloader/api.py
```
*Backend sẽ chạy tại địa chỉ: `http://127.0.0.1:8003`*

#### 2. Khởi động Frontend (Next.js)
Mở một terminal mới tại thư mục `frontends/socialpeta_downloader`:
```bash
# Cài đặt thư viện (nếu chạy lần đầu)
npm install

# Khởi chạy dev server
npm run dev
```
*Frontend sẽ chạy tại địa chỉ: `http://localhost:3000`*

#### 3. Khởi động Electron Container (Tùy chọn)
Nếu bạn muốn debug giao diện ứng dụng dưới dạng app Desktop Electron:
```bash
cd electron
npm install
npm start
```

---

## 📦 Hướng Dẫn Đóng Gói Ứng Dung (Build Electron)

Dự án cung cấp script `scripts/build.py` hỗ trợ đóng gói chéo nền tảng (hỗ trợ Windows, macOS, Linux).

### Các bước đóng gói:

1. Đảm bảo môi trường ảo `.venv` đã cài đặt đầy đủ thư viện trong `requirements.txt` bao gồm cả `pyinstaller`.
2. Mở terminal tại thư mục gốc dự án và chạy:
   ```bash
   .venv\Scripts\python.exe scripts/build.py
   ```
   *(Thay thế đường dẫn `.venv/bin/python` tương ứng nếu bạn đang chạy trên macOS/Linux).*

### Quá trình tự động của Build Script:
- **Bước 1 (Build Frontend)**: Trình đóng gói thực hiện `npm run build` Next.js để xuất ra thư mục tĩnh dạng HTML/CSS/JS tại `frontends/socialpeta_downloader/out`.
- **Bước 2 (Compile Python Backend)**: Sử dụng `PyInstaller` biên dịch mã nguồn Python backend thành một tệp thực thi duy nhất (`api.exe` trên Windows hoặc tệp nhị phân `api` trên macOS/Linux).
- **Bước 3 (Copy resources)**: Sao chép tệp thực thi API vào thư mục `electron/resources/` và tài nguyên Frontend tĩnh vào `electron/frontend/`.
- **Bước 4 (Package Electron App)**: Thực thi `npm run dist` tại thư mục `electron` để tạo bộ cài đặt ứng dụng Desktop hoàn chỉnh (sử dụng NSIS Installer trên Windows lưu tại thư mục `electron/dist/`).

---

## 🛠️ Yêu Cầu Hệ Thống (Requirements)
- **Node.js**: Phiên bản `>= 18.0.0`
- **Python**: Phiên bản `>= 3.10`
- **FFmpeg & FFprobe**: Cần cài đặt sẵn trong hệ thống và đưa vào biến môi trường `PATH` để sử dụng tính năng tính toán `dHash` của video.
- **Google Chrome**: Khuyến nghị cài đặt phiên bản mới nhất để Playwright kết nối CDP qua cổng debug.
