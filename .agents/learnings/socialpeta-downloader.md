# SocialPeta Downloader

> Tổng hợp kiến thức về công cụ tự động hóa tải video SocialPeta trong dự án.
> Cập nhật lần cuối: 2026-06-01

---

## Architecture

### FastAPI Backend & Next.js Integration
- **Ngày**: 2026-06-01
- **Chi tiết**: Sử dụng kiến trúc Client-Server: Backend FastAPI (`port 8003`) điều khiển Playwright CDP qua cổng debug `9222` của Chrome, đồng thời cung cấp các REST endpoints và kết nối WebSocket để Next.js Frontend (`port 3000`) hiển thị tiến độ và logs thời gian thực.
- **Files liên quan**: `tools/socialpeta_downloader/api.py`, `tools/socialpeta_downloader/api/routes.py`, `frontends/socialpeta_downloader/app/page.js`

### Single Chrome Control
- **Ngày**: 2026-06-01
- **Chi tiết**: Tách biệt luồng kết nối và luồng kiểm soát tab. Trình duyệt Chrome debug port được khởi động trực tiếp ở trạng thái `about:blank` để người dùng hoàn toàn kiểm soát việc điều hướng thủ công, tránh xung đột mở nhiều tab hoặc tạo cửa sổ trình duyệt login dư thừa.
- **Files liên quan**: `tools/socialpeta_downloader/core.py`, `tools/socialpeta_downloader/api/routes.py`

### Multi-Client WebSocket Log Broadcasting (Pub-Sub Pattern)
- **Ngày**: 2026-06-01
- **Chi tiết**: Giải quyết vấn đề mất log khi nhiều Client kết nối WebSocket bằng cách thiết lập danh sách log subscribers. Mỗi kết nối WebSocket sở hữu một log queue riêng trong bộ nhớ. Hàm log của core engine tự động nhân bản tin nhắn tới tất cả log queues của subscribers đang kết nối, đảm bảo phân phối log chính xác, bất đồng bộ và an toàn.
- **Files liên quan**: `tools/socialpeta_downloader/core/__init__.py`, `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/api/routes.py`

### dHash Video Metadata Caching
- **Ngày**: 2026-06-01
- **Chi tiết**: Để tránh việc ffmpeg bị gọi lặp lại nhiều lần gây quá tải CPU khi kiểm tra trùng lặp (duplicate check), mã dHash được tính một lần duy nhất cho mỗi video và lưu lại trực tiếp trong JSON metadata. Các lần kiểm tra sau sẽ đọc trực tiếp từ cache này.
- **Files liên quan**: `tools/socialpeta_downloader/core/deduplication.py`

### Native DevTools HTTP API for Tab Discovery
- **Ngày**: 2026-06-01
- **Chi tiết**: Thay vì khởi động và đóng các instance Playwright CDP liên tục để dò tìm danh sách tab (gây tốn tài nguyên và dễ xung đột kết nối), backend truy vấn trực tiếp HTTP endpoint `/json/list` của Chrome trên cổng debug. Cách này chạy cực nhanh (dưới 5ms), tốn 0% CPU bổ sung và không tạo subprocess.
- **Files liên quan**: `tools/socialpeta_downloader/core/tab_manager.py`

---

## Bugs & Solutions

### RLock memory leak khi cào file ngẫu nhiên liên tục
- **Ngày**: 2026-06-01
- **Vấn đề**: Việc tạo và lưu trữ `threading.RLock()` cho từng đường dẫn file trong `item_locks` mà không có cơ chế dọn dẹp gây rò rỉ bộ nhớ (leak locks) khi chạy thời gian dài với số lượng ad lớn.
- **Root cause**: Từ khóa dict `self.item_locks[fpath]` không bao giờ bị xóa sau khi luồng xử lý xong file.
- **Fix**: Định nghĩa lớp `RefCountedLock` để bọc `RLock` và theo dõi số lượng tham chiếu (reference counter). Khi counter giảm về 0, khóa sẽ tự động được xóa khỏi dict `self.item_locks`.
- **Files liên quan**: `tools/socialpeta_downloader/core/utils.py`

### Treo luồng (Subprocess Hang) do thiếu timeout khi gọi FFmpeg/FFprobe
- **Ngày**: 2026-06-01
- **Vấn đề**: Các tiến trình con (`ffmpeg`/`ffprobe`) thỉnh thoảng bị treo vô hạn (zombie process hoặc deadlock) khi xử lý video bị lỗi hoặc luồng I/O bị chặn.
- **Root cause**: Gọi `subprocess.run()` không thiết lập tham số `timeout`.
- **Fix**: Thêm tham số `timeout=30` và `timeout=15` vào tất cả các lời gọi `subprocess.run` trong deduplication engine.
- **Files liên quan**: `tools/socialpeta_downloader/core/deduplication.py`

### Race condition khi đọc file báo cáo CSV đồng thời từ API
- **Ngày**: 2026-06-01
- **Vấn đề**: Lỗi `PermissionError` hoặc dữ liệu rác khi người dùng gọi API xem/tải CSV báo cáo đúng lúc luồng ghi tải đang ghi dữ liệu vào file.
- **Root cause**: API `get_report` và `export_report` đọc trực tiếp file CSV mà không dùng chung lock ghi dữ liệu.
- **Fix**: Bọc toàn bộ logic đọc file CSV trong `get_report` và `export_report` bằng `core.metadata_lock`, đồng thời trả về nội dung file thông qua FastAPI `Response` thay vì `FileResponse` để giải phóng lock an toàn và ngay lập tức.
- **Files liên quan**: `tools/socialpeta_downloader/api/routes.py`

### Lỗi type checking và trùng lặp override signature giữa các mixin class
- **Ngày**: 2026-06-01
- **Vấn đề**: Pyright báo lỗi override signature không tương thích do sự khác biệt về kiểu trả về (`threading.RLock` vs `RefCountedLock`) và tên các đối số truyền vào giữa các Mixin.
- **Root cause**: Định nghĩa các stubs khai báo hàm trong mixin con khác với kiểu thực tế cài đặt ở mixin cha.
- **Fix**: Đồng bộ hóa toàn bộ signatures, đổi kiểu trả về của `get_item_lock` thành `Any` ở các file mixin stubs, và chuẩn hóa các tên đối số (`new_file`, `file_path`, `p`) thống nhất ở cả nơi khai báo và triển khai.
- **Files liên quan**: `tools/socialpeta_downloader/core/downloader.py`, `tools/socialpeta_downloader/core/legacy_scraper.py`, `tools/socialpeta_downloader/core/utils.py`

### WebSocket log mất khi có 2 client kết nối đồng thời
- **Ngày**: 2026-06-01
- **Vấn đề**: Khi có từ 2 client kết nối WebSocket, log chỉ hiển thị ngẫu nhiên trên một trong các client và bị mất ở các client còn lại.
- **Root cause**: Sử dụng một queue chung `core.log_queue`. Khi một client gọi `.get_nowait()`, phần tử đó sẽ bị xóa khỏi queue dùng chung khiến các client khác không nhận được.
- **Fix**: Chuyển đổi sang mô hình Publisher-Subscriber (Pub-Sub): lưu danh sách `log_subscribers = []` (chứa các queue độc lập của mỗi client). Khi ghi log mới, đẩy bản sao tin nhắn vào tất cả queue trong danh sách.
- **Files liên quan**: `tools/socialpeta_downloader/core/__init__.py`, `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/api/routes.py`

### CPU Spike & Disk I/O do quét đĩa liên tục (FIFO Disk Scan)
- **Ngày**: 2026-06-01
- **Vấn đề**: Vòng lặp hiển thị tiến độ trong `run_crawler.py` và `cli.py` liên tục quét thư mục tạm `.temp` và đọc tất cả các file JSON để đếm số lượng item đang chờ (pending) và đang tải (downloading), gây quá tải CPU và Disk I/O.
- **Root cause**: Quét ổ đĩa bằng `os.listdir` và parse JSON trực tiếp theo chu kỳ ngắn.
- **Fix**: Duy trì đếm trạng thái `pending` và `downloading` trong bộ nhớ thông qua thuộc tính `core.stats` đã được đồng bộ hóa thread-safe. Các bộ giám sát UI chỉ cần truy cập thuộc tính này từ bộ nhớ thay vì quét đĩa.
- **Files liên quan**: `tools/socialpeta_downloader/core/__init__.py`, `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/cli/cli.py`, `tools/socialpeta_downloader/scripts/run_crawler.py`

### Silent failure khi tải lỗi trong Downloader Worker
- **Ngày**: 2026-06-01
- **Vấn đề**: Khi downloader worker gặp lỗi tải file CDN (403 Forbidden, hết hạn link, timeout) hoặc lỗi di chuyển file unique, hệ thống không cập nhật lỗi rõ ràng lên UI, khiến người dùng thấy tiến trình tải bị đứng im.
- **Root cause**: Worker in lỗi ra stdout bằng lệnh `print(f"[-] Loi...")` thay vì gọi logger của hệ thống dẫn đến thông báo không truyền được qua WebSocket/Logs.
- **Fix**: Thay thế toàn bộ các print thông báo lỗi trong worker downloader và stream 3 filter thành `self.log("error", ...)`.
- **Files liên quan**: `tools/socialpeta_downloader/core/downloader.py`

### Lỗi khởi động API uvicorn do trùng tên thư mục api và file api.py
- **Ngày**: 2026-06-01
- **Vấn đề**: Khi uvicorn chạy ở chế độ dev với chuỗi nạp module `"socialpeta_downloader.api:app"`, Python tự động tìm thấy folder `api` trước file `api.py` và báo lỗi không tìm thấy đối tượng `app`.
- **Root cause**: Xung đột phân giải package trong Python giữa thư mục `api/` và file `api.py` tại cùng một cấp thư mục.
- **Fix**: Khởi chạy `uvicorn.run(app, ...)` trực tiếp bằng đối tượng `app` thay vì chuỗi import, đồng thời đổi default `SOCIALPETA_DOWNLOADER_PORT` từ 9222 sang 8003 để tránh xung đột cổng debug của Chrome.
- **Files liên quan**: `tools/socialpeta_downloader/api.py`, `tools/socialpeta_downloader/config.py`

### Socket Forbidden Error 10013 (Cổng 8003 bị chiếm)
- **Ngày**: 2026-06-01
- **Vấn đề**: Backend FastAPI không khởi động được và báo lỗi socket [WinError 10013].
- **Root cause**: Phiên bản compiled `api.exe` đã được cài đặt và đang chạy ngầm trong hệ thống, chiếm dụng cổng `8003`.
- **Fix**: Sử dụng `netstat -ano | findstr :8003` để tìm PID của tiến trình chạy ngầm, sau đó dùng `taskkill /f /pid <PID>` để giải phóng cổng trước khi chạy uvicorn ở chế độ dev.
- **Files liên quan**: N/A

### Lỗi khởi chạy 2 trình duyệt Chrome cùng lúc khi kết nối
- **Ngày**: 2026-06-01
- **Vấn đề**: Khi người dùng nhấn nút kết nối, 2 cửa sổ Chrome được mở lên (một cửa sổ debug port của default profile mở SocialPeta và một cửa sổ headed persistent browser phụ).
- **Root cause**: `check_login_status` cố gắng mở tab SocialPeta qua CDP khi chưa phát hiện tab hoạt động, đồng thời luồng đăng nhập fallback khởi chạy thêm một trình duyệt headed mới.
- **Fix**: Đơn giản hóa `check_login_status` để chỉ thử nghiệm kết nối cổng CDP. Đổi URL khởi chạy Chrome thành `about:blank` và loại bỏ hoàn toàn cơ chế tự khởi chạy cửa sổ persistent browser phụ trong `run_login_flow`.
- **Files liên quan**: `tools/socialpeta_downloader/core.py`

### Lỗi hiển thị đỏ (Unresolved Attribute Warnings) trong các file Mixin của Core Engine
- **Ngày**: 2026-06-01
- **Vấn đề**: IDE (Pylance/Pyright) cảnh báo màu đỏ hàng loạt lỗi "unresolved attribute/method" cho các biến và phương thức được truy cập qua `self` trong các Mixin.
- **Root cause**: Phân tích tĩnh của IDE không thể tự động liên kết các thuộc tính/phương thức động được thừa kế chéo giữa các Mixins trong cấu trúc đa kế thừa.
- **Fix**: Định nghĩa các type annotations và import các thư viện phụ thuộc (`queue`, `threading`, `typing`) ngay trên đầu của tất cả các lớp Mixin để khai báo các thuộc tính mong đợi.
- **Files liên quan**: `tools/socialpeta_downloader/core/session.py`, `tools/socialpeta_downloader/core/deduplication.py`, `tools/socialpeta_downloader/core/downloader.py`, `tools/socialpeta_downloader/core/legacy_scraper.py`, `tools/socialpeta_downloader/core/legacy_sniffer.py`, `tools/socialpeta_downloader/core/sniffer.py`

### CPU Spike khi check duplicate (FFmpeg dHash gọi liên tục)
- **Ngày**: 2026-06-01
- **Vấn đề**: Quá trình deduplication gọi FFmpeg lặp lại nhiều lần trên cùng một video để tính dHash, làm quá tải CPU.
- **Root cause**: Thiếu cơ chế lưu trữ cache dHash cho video đã được phân tích.
- **Fix**: Tạo cache trong JSON metadata để lưu dHash sau khi tính toán lần đầu. Các lần check tiếp theo sẽ đọc từ cache thay vì gọi FFmpeg.
- **Files liên quan**: `tools/socialpeta_downloader/core/deduplication.py`

### Multi-client port conflict (settings.CHROME_DEBUG_PORT bị ghi đè global)
- **Ngày**: 2026-06-01
- **Vấn đề**: Nhiều clients gọi API với các cổng debug khác nhau làm thay đổi biến cấu hình toàn cục `settings.CHROME_DEBUG_PORT`, gây lỗi kết nối chéo giữa các client.
- **Root cause**: API endpoints ghi đè trực tiếp thuộc tính toàn cục `settings.CHROME_DEBUG_PORT`.
- **Fix**: Loại bỏ việc ghi đè biến cấu hình toàn cục. Truyền port động như một tham số context trực tiếp từ API endpoint xuống các phương thức của core engine.
- **Files liên quan**: `tools/socialpeta_downloader/api/routes.py`, `tools/socialpeta_downloader/core/chrome.py`, `tools/socialpeta_downloader/core/tab_manager.py`

### Kiểm tra Chrome debug port không chính xác (Socket thô nhận diện nhầm service khác)
- **Ngày**: 2026-06-01
- **Vấn đề**: Sử dụng socket kết nối thô để kiểm tra cổng debug của Chrome có thể nhận diện sai các dịch vụ khác đang lắng nghe trên cùng cổng.
- **Root cause**: Socket chỉ kiểm tra kết nối TCP cấp thấp mà không xác nhận giao thức CDP của Chrome.
- **Fix**: Gửi HTTP GET request đến endpoint `/json/version` để xác nhận phản hồi hợp lệ từ Chrome Remote Debugging.
- **Files liên quan**: `tools/socialpeta_downloader/core/chrome.py`

### Lỗ hổng bảo mật SSRF (URL không được validate trước khi page.goto)
- **Ngày**: 2026-06-01
- **Vấn đề**: Trình duyệt có thể được điều hướng đến bất kỳ trang web độc hại nào thông qua tham số URL đầu vào.
- **Root cause**: Thiếu bước kiểm tra tính hợp lệ của domain trước khi gọi `page.goto()`.
- **Fix**: Thêm bộ lọc `is_safe_url` kiểm tra chỉ cho phép các URL thuộc domain `socialpeta.com` hoặc `guangdada.com` (và subdomains tương ứng).
- **Files liên quan**: `tools/socialpeta_downloader/core/legacy_scraper.py`

### Build script chỉ hoạt động trên Windows (Hardcoded paths)
- **Ngày**: 2026-06-01
- **Vấn đề**: Script `scripts/build.py` không thể chạy trên macOS hoặc Linux do các đường dẫn thư mục nhị phân ảo (Virtual Env) và tên tệp thực thi bị hardcode kiểu Windows (`api.exe`, `.venv/Scripts`).
- **Root cause**: Thiếu xử lý chéo nền tảng (cross-platform path resolution).
- **Fix**: Sử dụng `sys.platform` để xác định động thư mục nhị phân (`Scripts` trên Windows vs `bin` trên Unix) và phần mở rộng tệp thực thi (`api.exe` vs `api`).
- **Files liên quan**: `scripts/build.py`

### Sập/Treo tiến trình Backend khi tắt/đóng tab kết nối (Node.js EPIPE Error)
- **Ngày**: 2026-06-01
- **Vấn đề**: Khi người dùng tắt/đóng tab hoặc kết thúc tiến trình cào, backend Python bị crash âm thầm và tự khởi động lại (gây mất tiến trình cào đang chạy). logs ghi nhận lỗi `node:events:487 throw er; // Unhandled 'error' event Error: EPIPE: broken pipe, write`.
- **Root cause**: Polling `/tabs` liên tục tạo và đóng các kết nối Playwright CDP qua cổng 9222. Khi một kết nối bị đóng trong khi các thread khác hoặc chính nó đang cố gửi tin qua socket, Node.js driver của Playwright gặp lỗi ghi ống dẫn (broken pipe) không xử lý được và crash toàn bộ subprocess, kéo theo parent Python process sập.
- **Fix**: (1) Thay thế hoàn toàn Playwright trong `detect_tabs` bằng truy cập HTTP direct `/json/list`, (2) Loại bỏ listener `response` của `page` trong khối `finally` trước khi gọi `browser.close()` để ngắt tất cả các event ghi dữ liệu qua pipe đang chuẩn bị đóng, (3) Đơn giản hóa `check_login_status` chỉ kiểm tra active port thay vì tạo CDP.
- **Files liên quan**: `tools/socialpeta_downloader/core/tab_manager.py`, `tools/socialpeta_downloader/core/chrome.py`

---

## How-To

### Cách khởi động và debug dự án ở chế độ phát triển (Dev Mode)
- **Ngày**: 2026-06-01
- **Bước thực hiện**:
  1. Khởi động Backend API:
     Chạy PowerShell tại thư mục gốc: `$env:PYTHONPATH="tools"; .venv\Scripts\python.exe tools/socialpeta_downloader/api.py`
  2. Khởi động Frontend:
     Chạy lệnh tại thư mục `frontends/socialpeta_downloader`: `npm run dev`
  3. Mở Chrome với cổng debug 9222 và truy cập `http://localhost:3000`.
- **Files liên quan**: `tools/socialpeta_downloader/api.py`, `frontends/socialpeta_downloader/package.json`

### Cách đóng gói ứng dụng Electron hoàn chỉnh
- **Ngày**: 2026-06-01
- **Bước thực hiện**:
  1. Đảm bảo môi trường ảo `.venv` đã được cài đặt đầy đủ dependencies.
  2. Chạy script đóng gói tại thư mục gốc: `.venv\Scripts\python.exe scripts/build.py`
  3. Script sẽ tự động build Next.js tĩnh, biên dịch Python sang `api.exe` (hoặc `api` trên macOS/Linux) thông qua PyInstaller, đồng bộ tài nguyên vào cấu trúc Electron, và tạo bộ cài đặt NSIS duy nhất tại `electron/dist/`.
- **Files liên quan**: `scripts/build.py`, `electron/package.json`

---

## Patterns

### Tải file trực tiếp từ Backend API
- **Ngày**: 2026-06-01
- **Chi tiết**: Để tránh các vấn đề CORS và giới hạn context khi tải file qua API fetch thông thường, sử dụng `window.open` trỏ trực tiếp đến endpoint của backend trả về `FileResponse` (CSV export).
- **Ví dụ code**:
  ```javascript
  const handleExportCSV = () => {
    window.open("http://localhost:8003/api/v1/socialpeta/export", "_blank");
    addLog("success", "Đã xuất dữ liệu download_info.csv thành công!");
  };
  ```
- **Files liên quan**: `frontends/socialpeta_downloader/app/page.js`

### Dynamic Port Parameterization (Truyền cổng động)
- **Ngày**: 2026-06-01
- **Chi tiết**: Cho phép Client ghi đè động cổng debug Chrome của server thông qua query parameter hoặc request body mà không làm thay đổi biến cấu hình toàn cục.
- **Ví dụ code**:
  ```python
  @router.get("/status")
  def get_status(port: Optional[int] = None):
      port_val = port if port is not None else settings.CHROME_DEBUG_PORT
      chrome_connected = core.check_and_launch_chrome(port_val)
      ...
  ```
- **Files liên quan**: `tools/socialpeta_downloader/api/routes.py`, `tools/socialpeta_downloader/core/chrome.py`

### Two-stage Connection Check & Launch UX Pattern
- **Ngày**: 2026-06-01
- **Chi tiết**: Giải quyết tình trạng UI chờ kết nối vô hạn hoặc khởi chạy trình duyệt phụ không cần thiết. Hệ thống kiểm tra socket thụ động ở cổng debug trước để phân biệt trạng thái: (1) Chrome debug đang chạy -> kết nối trực tiếp, (2) Chrome chưa chạy -> thông báo rõ ràng trên UI nút bấm, sau đó tiến hành khởi chạy mới.
- **Files liên quan**: `tools/socialpeta_downloader/routes.py`, `frontends/socialpeta_downloader/app/page.js`

### CDP Target Matching via Persistent Target ID
- **Ngày**: 2026-06-01
- **Chi tiết**: Sử dụng persistent Target ID của Chrome DevTools thay vì tự động phát sinh và tiêm một biến Javascript `window.__tab_id` tạm thời dễ bị mất khi tải lại trang (reload). Kết nối và so khớp các trang thông qua CDPSession của Playwright.
- **Ví dụ code**:
  ```python
  client = context.new_cdp_session(page)
  target_info = client.send("Target.getTargetInfo")
  target_id = target_info.get("targetInfo", {}).get("targetId")
  ```
- **Files liên quan**: `tools/socialpeta_downloader/core/tab_manager.py`
