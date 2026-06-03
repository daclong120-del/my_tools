# SocialPeta Downloader

> Tổng hợp kiến thức về công cụ tự động hóa tải video SocialPeta trong dự án.
> Cập nhật lần cuối: 2026-06-03

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

### Self-Contained Download Workspaces
- **Ngày**: 2026-06-02
- **Chi tiết**: Biến đổi thư mục tải xuống thành một Workspace độc lập hoàn chỉnh chứa: `db.sqlite3` (lưu trạng thái phiên cào và lịch sử tải), `download_info.csv` (lịch sử tải được đồng bộ), `duplicate_audit.csv` (lịch sử lọc trùng). Việc lưu trữ `saved_path` dưới dạng đường dẫn tương đối (Relative Path) giúp toàn bộ Workspace có tính di động tuyệt đối khi di chuyển sang ổ đĩa hoặc máy khác mà không bị hỏng liên kết tệp tin.
- **Files liên quan**: `tools/socialpeta_downloader/config.py`, `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/core/session.py`

### CLI V2 Terminal User Interface (TUI)
- **Ngày**: 2026-06-02
- **Chi tiết**: Thiết kế giao diện CLI tương tác (TUI) bằng `InquirerPy` (sử dụng phím mũi tên) kết hợp Live Dashboard của `rich` để hiển thị trực quan trạng thái tải/cào đa luồng. Hỗ trợ cơ chế dừng khẩn cấp bằng phím tắt `Ctrl + Q` để ngắt luồng workers an toàn và dọn dẹp các tệp tạm trên đĩa.
- **Files liên quan**: `tools/socialpeta_downloader/cli/cli_v2/cli.py`

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

### Nuốt lỗi hệ thống âm thầm (System errors swallowed silently without logging)
- **Ngày**: 2026-06-02
- **Vấn đề**: Nhiều khối `try...except` trong codebase sử dụng `except Exception: pass` hoặc chỉ in ra console bằng `print()` mà không lưu lại traceback đầy đủ.
- **Root cause**: Thiếu cơ chế ghi log traceback chi tiết cho các lỗi phát sinh trong luồng xử lý bất đồng bộ hoặc background workers.
- **Fix**: Quét toàn bộ codebase và thay thế các print hoặc pass không an sau bằng `import traceback` và ghi log chi tiết thông qua `self.log("error", ...)` hoặc `core.log("error", ...)` chứa `traceback.format_exc()`.
- **Files liên quan**: `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/core/__init__.py`, `tools/socialpeta_downloader/core/chrome.py`, `tools/socialpeta_downloader/core/deduplication.py`, `tools/socialpeta_downloader/core/session.py`, `tools/socialpeta_downloader/core/downloader.py`, `tools/socialpeta_downloader/core/sniffer.py`, `tools/socialpeta_downloader/core/youtube.py`, `tools/socialpeta_downloader/api/routes.py`, `tools/socialpeta_downloader/sys_monitor.py`

### Lỗi âm số lượng hàng chờ (Negative Pending Count) do lệch total_sniffed & YouTube extraction fail
- **Ngày**: 2026-06-02
- **Vấn đề**: Số lượng hàng chờ (pending count) hiển thị số âm trên giao diện và sai lệch giữa các chỉ số thống kê.
- **Root cause**: (1) Frontend tính toán pending bằng công thức thủ công `total_sniffed - done - failed - duplicate` thay vì dùng trực tiếp `stats.pending` của backend, (2) Backend không lưu trạng thái `'pending'` cho các quảng cáo YouTube phải click khi phát hiện (`youtube_click_required`), khiến khi quá trình click/trích xuất thất bại, `stats['failed']` tăng 1 nhưng `total_sniffed` không tăng, dẫn đến tổng số âm, (3) Tồn tại nhiều nơi tự tăng `total_sniffed` thủ công trong các file sniffer/youtube dẫn đến double-increment khi thành công.
- **Fix**: (1) Đồng bộ hóa việc tăng `total_sniffed` duy nhất trong `_write_item_file` khi `old_status` là `None` (lần đầu tạo ad), loại bỏ tất cả các lệnh tăng `total_sniffed` thủ công khác, (2) Lưu trạng thái `"pending"` cho quảng cáo YouTube ngay khi đưa vào hàng đợi trích xuất, (3) Cập nhật frontend Next.js sử dụng trực tiếp `data.stats.pending` và `data.stats.downloading` từ API/WebSocket.
- **Files liên quan**: `tools/socialpeta_downloader/core/utils.py`, `tools/socialpeta_downloader/core/sniffer.py`, `tools/socialpeta_downloader/core/legacy_sniffer.py`, `tools/socialpeta_downloader/core/youtube.py`, `frontends/socialpeta_downloader/app/page.js`

### App treo cứng ở luồng tải do Socket Read Timeout
- **Ngày**: 2026-06-02
- **Vấn đề**: Luồng tải dừng lại ở log read timed out của requests CDN và treo cứng toàn bộ ứng dụng.
- **Root cause**: Mặc định `requests.get` với `timeout=20` chỉ giới hạn thời gian kết nối/nhận headers. Khi tải qua `response.iter_content` ở dạng stream, socket đọc dữ liệu không có timeout và bị block vô hạn khi mạng chập chờn.
- **Fix**: Thiết lập timeout trực tiếp lên socket đọc thô: `if response.raw and response.raw.connection: response.raw.connection.sock.settimeout(20.0)`.
- **Files liên quan**: `tools/socialpeta_downloader/core/downloader.py`

### Kẹt hàng đợi lọc trùng khi thiếu FFmpeg/FFprobe
- **Ngày**: 2026-06-02
- **Vấn đề**: Video tải về thành công bị kẹt vĩnh viễn ở thư mục tạm `.temp` với tên hash, không bao giờ được lọc và di chuyển sang thư mục đích.
- **Root cause**: Khi thiếu FFmpeg/FFprobe, hệ thống ném exception và thực hiện `return` thoát luồng hoàn toàn, làm cho hàng đợi `filter_queue` bị kẹt.
- **Fix**: Sử dụng biến flag `ffmpeg_available` (mặc định bằng `True`). Khi check FFmpeg lỗi, ghi nhận log cảnh báo và gán `ffmpeg_available = False` thay vì thoát luồng. Nếu `ffmpeg_available` là `False`, thực hiện sao chép/di chuyển trực tiếp video sang thư mục đích (fallback).
- **Files liên quan**: `tools/socialpeta_downloader/core/downloader.py`

### Thiếu FFmpeg khi đóng gói trên máy build
- **Ngày**: 2026-06-02
- **Vấn đề**: Trình đóng gói `build.py` không tìm thấy FFmpeg do máy build không cài đặt PATH.
- **Root cause**: Script build chỉ tìm kiếm FFmpeg qua `shutil.which` trong biến môi trường PATH.
- **Fix**: Cập nhật `build.py` ưu tiên tìm kiếm `ffmpeg.exe` và `ffprobe.exe` trong thư mục tĩnh dự án `resources/bin/` trước khi fallback tìm qua PATH.
- **Files liên quan**: `scripts/build.py`

### Lỗi NameError: name 'settings' is not defined trong migrate_old_data
- **Ngày**: 2026-06-02
- **Vấn đề**: Backend API bị crash khi khởi động do unhandled exception.
- **Root cause**: Lời gọi `settings.DATA_DIR` trong `migrate_old_data` của `session.py` bị thiếu import cấu hình `settings` toàn cục.
- **Fix**: Thêm import `from socialpeta_downloader.config import settings` ở đầu file `session.py`.
- **Files liên quan**: `tools/socialpeta_downloader/core/session.py`

### Lỗi biên dịch cú pháp trong file CMD/BAT (Windows) do bảng mã ký tự đặc biệt
- **Ngày**: 2026-06-02
- **Vấn đề**: Khởi chạy `run.bat` bị lỗi cú pháp `') else (' is not recognized as an internal or external command` hoặc `'ủa'`... và tự đóng terminal ngay lập tức.
- **Root cause**: Trình thông dịch CMD mặc định của Windows phân giải sai cấu trúc khối lệnh `if/else` khi gặp các ký tự tiếng Việt có dấu trong câu lệnh `echo` hoặc comment.
- **Fix**: Loại bỏ hoàn toàn các ký tự tiếng Việt có dấu trong file `run.bat` (chuyển sang dạng không dấu chuẩn ASCII).
- **Files liên quan**: `tools/socialpeta_downloader/cli/cli_v2/run.bat`

### Lỗi thiếu thư viện Tcl/Tk của Tkinter trong môi trường ảo (.venv)
- **Ngày**: 2026-06-02
- **Vấn đề**: Khi mở cửa sổ chọn Folder Explorer bằng `tkinter` trên Windows, chương trình báo lỗi thiếu tệp cấu hình `init.tcl` (`Can't find a usable init.tcl`).
- **Root cause**: Trình khởi tạo môi trường ảo Python trên Windows không tự động sao chép hoặc liên kết chính xác thư mục thư viện Tcl từ cài đặt gốc.
- **Fix**: Sao chép thư mục `tcl` từ Python gốc trên hệ thống (ví dụ: `Python313/tcl`) trực tiếp vào thư mục gốc của `.venv` của dự án (`.venv/tcl`).
- **Files liên quan**: N/A

### Lỗi bỏ sót tải video YouTube có thời lượng 0s
- **Ngày**: 2026-06-02
- **Vấn đề**: Video YouTube có thông số duration trong header bằng `0` bị bộ lọc sniffer nhận diện sai thành định dạng hình ảnh và bỏ qua không tải.
- **Root cause**: Logic phân loại kiểu file dựa trên `duration` coi duration = 0 là ảnh.
- **Fix**: Cập nhật logic phân loại, ưu tiên kiểm tra sự hiện diện của URL YouTube hợp lệ để gán loại là `youtube_video` trước khi dựa vào thông số duration.
- **Files liên quan**: `tools/socialpeta_downloader/core/utils.py`

### ValueError 'N/A' khi gọi ffprobe trên hình ảnh trong lịch sử lọc trùng
- **Ngày**: 2026-06-02
- **Vấn đề**: Chương trình in ra cảnh báo lỗi `ValueError: could not convert string to float: 'N/A'` liên tục khi chạy lọc trùng.
- **Root cause**: `download_history` lưu cả lịch sử hình ảnh và video. Khi lọc trùng, chương trình chạy qua tất cả file đã tải, trong đó file ảnh không có duration khiến `ffprobe` trả về `N/A`.
- **Fix**: Lỗi đã được xử lý dự phòng bằng khối `try...except` trả về giá trị `-1.0` an toàn nên không gây sập ứng dụng.
- **Files liên quan**: `tools/socialpeta_downloader/core/deduplication.py`

### Lỗi nạp _greenlet.pyd (LoadLibraryExW ImportError) trên máy không cài VC++ Runtime
- **Ngày**: 2026-06-03
- **Vấn đề**: File `.exe` đóng gói bằng Nuitka khi chạy trên máy tính khác (máy ảo sạch, Windows Sandbox, hoặc máy chưa cài Visual C++ Redistributable) bị crash ngay khi khởi động và báo lỗi: `ImportError: LoadLibraryExW '...\_greenlet.pyd' failed: The specified module could not be found.`
- **Root cause**: Trình biên dịch Nuitka không tự động đóng gói các thư viện liên kết động C++ tiêu chuẩn như `msvcp140.dll` và các file liên quan (trong khi file `_greenlet.pyd` của Playwright biên dịch bằng C++ và yêu cầu chúng).
- **Fix**: Sao chép các file DLL C++ Runtime tiêu chuẩn (`msvcp140.dll`, `msvcp140_1.dll`, `msvcp140_2.dll`, `msvcp140_atomic_wait.dll`, `msvcp140_codecvt_ids.dll`, và `vcruntime140_threads.dll`) từ thư mục `C:\Windows\System32` của máy biên dịch trực tiếp vào thư mục gốc chứa file thực thi `.exe` của bản phân phối độc lập (dist).
- **Files liên quan**: `fast_build_cli_v2.bat`

### Lỗi sập Live Dashboard sớm do Stale State trong tab_states
- **Ngày**: 2026-06-03
- **Vấn đề**: Khi khởi chạy cào từ CLI V2, Live Dashboard kết thúc ngay lập tức trước khi luồng crawler bắt đầu chạy.
- **Root cause**: Trạng thái `status` của tab trong `tab_states` từ phiên chạy trước vẫn giữ giá trị `"done"`. Vòng lặp dashboard trong `cli.py` đọc giá trị này và thoát lập tức vì không thấy scraper hoạt động.
- **Fix**: Reset động trạng thái tab (`status = "new"`, `scraped_count = 0`, etc.) trong `cli.py` ngay trước khi khởi chạy luồng scraper và Live Dashboard.
- **Files liên quan**: `tools/socialpeta_downloader/cli/cli_v2/cli.py`

### Lỗi bỏ sót Trang 1 khi cào trong CLI V2
- **Ngày**: 2026-06-03
- **Vấn đề**: Khi yêu cầu cào Trang 1, hệ thống không tự chuyển sang Trang 2 rồi quay về Trang 1 để kích hoạt API tải lại dữ liệu mà dùng soft trigger không hiệu quả.
- **Root cause**: Khác biệt logic phân trang giữa CLI V1 và V2. V2 sử dụng `soft_trigger` (cuộn và tìm kiếm) thay vì thực hiện chuỗi click chuyển đổi trang thực sự (`click_sequence = [2, 1]`) như V1.
- **Fix**: Cập nhật logic sinh `click_sequence` động dựa trên trang hiện tại tương tự V1 để luôn đảm bảo thay đổi số trang thực tế trên giao diện, loại bỏ việc dùng soft trigger trong vòng lặp phân trang.
- **Files liên quan**: `tools/socialpeta_downloader/core/sniffer.py`

### Lỗi FileNotFoundError do thư mục tạm ở trạng thái Pending Deletion trên Windows
- **Ngày**: 2026-06-03
- **Vấn đề**: Biên dịch Nuitka bị crash với thông báo `FileNotFoundError: [Errno 2] No such file or directory` khi ghi các file const/C tạm trong thư mục `build\cli.build`.
- **Root cause**: Lệnh `rd /s /q build\cli.build` chạy ngay trước Nuitka làm Windows giữ thư mục ở trạng thái "pending deletion" không đồng bộ, khóa đường dẫn đó khiến Nuitka không thể ghi.
- **Fix**: Đổi tên thư mục cần xóa sang tên tạm ngẫu nhiên trước (ví dụ: `ren build\cli.build cli.build.old.%RANDOM%`), rồi mới xóa thư mục tạm đó, giúp giải phóng ngay lập tức đường dẫn ban đầu cho Nuitka.
- **Files liên quan**: `fast_build_cli_v2.bat`

### Lỗi biên dịch cú pháp của Windows Command Prompt (CMD) do bảng mã tiếng Việt UTF-8
- **Ngày**: 2026-06-03
- **Vấn đề**: File batch `.bat` bị lỗi cú pháp lệnh không hợp lệ (ví dụ: `'ROJECT_DIR' is not recognized`) hoặc tự đóng đột ngột.
- **Root cause**: Trình biên dịch lệnh CMD phân giải sai byte offsets khi đọc các ký tự UTF-8 tiếng Việt có dấu trong comments hoặc câu lệnh `echo`, gây lệch con trỏ lệnh tiếp theo.
- **Fix**: Loại bỏ toàn bộ ký tự tiếng Việt có dấu trong file batch, chuyển các comments và thông báo sang tiếng Việt không dấu chuẩn ASCII hoặc tiếng Anh.
- **Files liên quan**: `fast_build_cli_v2.bat`

### Lỗi bỏ sót video YouTube (YouTube Miss) do sai lệch quy trình click và sniffer
- **Ngày**: 2026-06-03
- **Vấn đề**: Tỷ lệ bỏ sót video YouTube cực kỳ cao khi cào trang SocialPeta, dù click vào ảnh vẫn không lấy được thông tin chi tiết của video YouTube.
- **Root cause**: (1) Trình sniffer nạp dữ liệu cũ hoặc không đồng bộ với sự kiện nhấp chuột. (2) Cơ chế click cũ vào vùng ảnh không đáng tin cậy. (3) CDN video được lấy song song và chèn đè lên trạng thái của YouTube ad ID trước khi worker YouTube kịp cào chi tiết.
- **Fix**:
  1. Ưu tiên xử lý YouTube: Khi nạp dữ liệu trang mới, sniffer lập tức phân loại các ad có nhãn nền tảng YouTube (`net-icon-youtube`), đánh dấu trạng thái ban đầu là `pending` với loại `youtube_video`, và đẩy ngay vào hàng đợi `youtube_queues` TRƯỚC KHI xử lý bất kỳ video CDN nào khác.
  2. Click chính xác vào icon: Nhắm mục tiêu click trực tiếp vào icon nền tảng YouTube ở góc dưới card quảng cáo (`.net-icon-youtube`), tăng độ tin cậy mở hộp popup.
  3. Tránh overwrite CDN: Khi sniffer bắt được request CDN của quảng cáo đang chờ YouTube click, nó không ghi đè trạng thái `pending` của YouTube ad mà lưu tạm file JSON vào thư mục tạm `tab{tab_index}`. Sau khi worker YouTube hoàn tất (hoặc scraper thread kết thúc), hệ thống sẽ quét dọn các file tạm này để tải CDN dự phòng nếu YouTube extraction thất bại.
- **Files liên quan**: `tools/socialpeta_downloader/core/sniffer.py`, `tools/socialpeta_downloader/core/youtube.py`, `tools/socialpeta_downloader/core/tab_manager.py`

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

### Cách khởi chạy nhanh CLI V2 trên Windows
- **Ngày**: 2026-06-02
- **Bước thực hiện**:
  1. Click đúp trực tiếp vào file: `tools/socialpeta_downloader/cli/cli_v2/run.bat`.
  2. Hoặc từ thư mục gốc của dự án trong CMD/PowerShell, chạy lệnh:
     `.\tools\socialpeta_downloader\cli\cli_v2\run.bat`
- **Files liên quan**: `tools/socialpeta_downloader/cli/cli_v2/run.bat`

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

### Dynamic Directory Initialization in Frozen Mode (Khởi tạo thư mục động khi đóng gói)
- **Ngày**: 2026-06-02
- **Chi tiết**: Để tránh việc đóng gói các file rác/temp của dev vào bộ cài đặt (installer) và đảm bảo quyền ghi ghi app chạy ở chế độ production, thư mục `data/` được loại bỏ khỏi `extraResources` của Electron. Thay vào đó, backend FastAPI (`api.exe`) tự động nhận diện chế độ chạy frozen (`sys.frozen`) để lấy đường dẫn thư mục cài đặt thực tế (`sys.executable`) và tự động khởi tạo các thư mục lưu trữ cần thiết (`data/videos`, `data/playwright_session`) khi chạy lần đầu.
- **Files liên quan**: `tools/socialpeta_downloader/config.py`, `electron/package.json`

### Bundling FFmpeg and FFprobe within Electron Installer (Tích hợp FFmpeg/FFprobe vào bộ cài)
- **Ngày**: 2026-06-02
- **Chi tiết**: Để tránh yêu cầu người dùng cuối phải cài đặt FFmpeg/FFprobe và cấu hình biến môi trường PATH thủ công, bộ cài đặt tự động tích hợp sẵn các file thực thi này. Script `build.py` sẽ quét tìm `ffmpeg` và `ffprobe` trên máy build (`shutil.which`), sao chép chúng vào thư mục `electron/resources/`. Cấu hình `package.json` (phần `extraResources`) sẽ đóng gói chúng vào app. Đồng thời, code backend tự động trỏ đến đường dẫn của bộ cài đặt này thông qua `settings.FFMPEG_PATH` và `settings.FFPROBE_PATH` khi ứng dụng chạy ở dạng frozen.
- **Files liên quan**: `scripts/build.py`, `electron/package.json`, `tools/socialpeta_downloader/config.py`, `tools/socialpeta_downloader/core/deduplication.py`, `tools/socialpeta_downloader/core/downloader.py`

### Thread-Safe SQL-to-CSV Synchronization
- **Ngày**: 2026-06-02
- **Chi tiết**: Thực hiện đồng bộ hóa một chiều thread-safe từ SQLite sang CSV (`download_info.csv` và `duplicate_audit.csv`) dưới khối khóa `history_lock` và SQLite WAL mode, đảm bảo file CSV luôn nhất quán, cập nhật trực quan cho người dùng mà không gây crash do xung đột ghi đồng thời từ nhiều worker.
- **Files liên quan**: `tools/socialpeta_downloader/core/session.py`

### In-Memory Configuration Override
- **Ngày**: 2026-06-02
- **Chi tiết**: Sử dụng một đối tượng trạng thái ứng dụng (`AppState` hoặc local variables) để lưu trữ tạm thời các thiết lập cổng debug, thư mục lưu trữ và số luồng xử lý do người dùng ghi đè thủ công tại CLI. Truyền các giá trị động này trực tiếp vào các service thay vì ghi đè biến cấu hình toàn cục, duy trì cấu trúc cấu hình gốc sạch sẽ.
- **Files liên quan**: `tools/socialpeta_downloader/cli/cli_v2/cli.py`

### Bundling MSVC C++ Redistributable DLLs for Standalone Nuitka Builds (Tích hợp VC++ Runtime vào bản đóng gói Nuitka)
- **Ngày**: 2026-06-03
- **Chi tiết**: Đối với các ứng dụng Python đóng gói standalone có sử dụng các thư viện C-extension như Playwright (`greenlet`), việc phân phối ứng dụng sang máy khách sạch thường bị lỗi DLL load failed do thiếu Microsoft C++ Runtime. Để giải quyết triệt để mà không bắt người dùng cài đặt gói Redistributable hệ thống, ta sao chép các tệp DLL runtime tiêu chuẩn của MSVC trực tiếp vào thư mục phân phối chứa tệp tin thực thi. Trình nạp của Windows sẽ ưu tiên tìm và tải các DLL này từ thư mục hiện hành của tiến trình.
- **Files liên quan**: `fast_build_cli_v2.bat`

### Prioritization & Safe Overwrite in Multi-Source Media Sniffing
- **Ngày**: 2026-06-03
- **Chi tiết**: Mẫu thiết kế để xử lý quảng cáo hỗ trợ nhiều nguồn đa phương tiện khác nhau (ví dụ: liên kết CDN tải trực tiếp và liên kết YouTube chính chủ). Ta thực hiện phân loại và đưa nguồn có độ ưu tiên cao nhất (YouTube) vào xử lý trước bằng hàng đợi. Đồng thời, khi bắt được các nguồn có độ ưu tiên thấp hơn (CDN) trong quá trình cào, ta không ghi đè trực tiếp để tránh mất dữ liệu nguồn chính, mà lưu tạm thông tin CDN vào một thư mục đệm. Khi luồng cào của tab kết thúc, ta thực hiện quét dọn thư mục đệm này và chỉ xếp hàng tải các CDN dự phòng nếu nguồn ưu tiên chính (YouTube) bị trích xuất thất bại.
- **Files liên quan**: `tools/socialpeta_downloader/core/sniffer.py`, `tools/socialpeta_downloader/core/tab_manager.py`
