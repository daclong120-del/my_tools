# Học hỏi từ quá trình sửa lỗi Crash Backend và Đóng gói lại ứng dụng

> Người viết: Antigravity
> Ngày: 2026-06-02
> Task: Sửa lỗi NameError: name 'settings' is not defined trong session.py khiến Backend không khởi động được trên máy người dùng cuối, sau đó đóng gói lại toàn bộ ứng dụng.

---

## 1. Approach & Reasoning (Cách tiếp cận & Suy luận)
Khi người dùng báo lỗi ứng dụng Electron không thể kết nối tới Backend API trên cổng `8003` và hiện cảnh báo "Failed to fetch", điểm xuất phát của tôi là kiểm tra xem tiến trình `api.exe` có đang chạy hay không. 
Nhìn vào danh sách tiến trình (`tasklist`), tôi phát hiện tiến trình API hoàn toàn không tồn tại. Tiếp tục truy vết vào file logs của Electron tại thư mục `AppData\Roaming\my-tools-desktop\backend.log`, tôi phát hiện lỗi unhandled exception khiến tiến trình crash ngay lập tức khi khởi chạy:
```
File "socialpeta_downloader\core\session.py", line 99, in migrate_old_data
NameError: name 'settings' is not defined
```
Lý do rất rõ ràng: Hàm `migrate_old_data` cố gắng truy cập thuộc tính `settings.DATA_DIR` để xác định đường dẫn cơ sở dữ liệu cũ, nhưng module `session.py` chưa hề import đối tượng `settings` từ `socialpeta_downloader.config`. Tôi đã tiến hành bổ sung import này để giải quyết triệt để lỗi NameError.

---

## 2. Roads Not Taken (Các ngả đường đã bỏ qua)
Tôi đã cân nhắc một số phương án khác trước khi thực hiện fix trực tiếp:
- **Truyền trực tiếp `DATA_DIR` qua tham số hàm**: Có thể sửa signature của `migrate_old_data(self, old_download_dir, default_data_dir)` và truyền biến này từ `__init__.py`. Tuy nhiên, cách này làm phức tạp hóa signature của hàm không cần thiết vì `settings` là cấu hình toàn cục tĩnh (static global config) của ứng dụng, việc import trực tiếp vào module có nhu cầu sử dụng là giải pháp sạch sẽ và chuẩn mực hơn.
- **Bọc khối try-except nuốt lỗi**: Một cách tiếp cận cẩu thả là bọc `settings.DATA_DIR` trong khối `try-except` và gán mặc định bằng một chuỗi hardcode nếu có lỗi. Tuy nhiên, điều này vi phạm nguyên tắc phát hiện lỗi sớm (fail-fast) và che giấu các lỗi nghiêm trọng về cấu hình.

---

## 3. How Things Connect (Mối liên kết hệ thống)
Ứng dụng của chúng ta hoạt động theo mô hình 3 lớp:
1. **Electron (Main Process)**: Khởi chạy và quản lý vòng đời của Backend (`api.exe`) và tải Frontend từ file HTML tĩnh.
2. **FastAPI Backend (api.exe)**: Cung cấp API dịch vụ, quản lý cơ sở dữ liệu lịch sử (`db.sqlite3`), đồng bộ dữ liệu ra CSV, và giao tiếp với Chrome qua CDP.
3. **Next.js (Frontend)**: Chạy trên Electron render process, gửi các request fetch tới Backend qua cổng `8003`.

Khi lớp thứ 2 (Backend) bị sập do lỗi NameError khi khởi chạy, lớp thứ 3 (Frontend) hoàn toàn không có điểm tựa để giao tiếp, dẫn đến lỗi "Failed to fetch" hiển thị trên UI.

---

## 4. Tools & Methods (Công cụ & Phương pháp)
- **Log Inspection**: Đọc trực tiếp file log ghi nhận từ luồng stdout/stderr của tiến trình con (`backend.log`) giúp định vị chính xác dòng code gây crash thay vì suy đoán mơ hồ.
- **Python Uvicorn Dev Server**: Khởi chạy API dạng script (`python tools/socialpeta_downloader/api.py`) để kiểm tra import và khởi động server tĩnh trước khi thực hiện build PyInstaller.
- **PyInstaller & electron-builder**: Dùng để đóng gói lại toàn bộ ứng dụng sau khi fix code để đảm bảo tệp phân phối cuối cùng (`api.exe` và bộ cài installer) hoạt động trơn tru.

---

## 5. Tradeoffs (Sự đánh đổi)
- **Đánh đổi thời gian build lấy độ tin cậy**: Việc chạy lại toàn bộ script `build.py` (bao gồm build Next.js, đóng gói PyInstaller và Electron) tốn khoảng 1-2 phút mỗi lần. Tuy nhiên, đây là bước bắt buộc để kiểm chứng xem phiên bản frozen (`api.exe`) có thực sự hoạt động ổn định trên môi trường máy khách hàng hay không.

---

## 6. Mistakes & Dead Ends (Sai lầm & Ngõ cụt)
- **Namespace Package Conflict**: Khi cố gắng chạy dev server bằng lệnh `uvicorn socialpeta_downloader.api:app`, tôi gặp lỗi `Attribute "app" not found` do Python ưu tiên resolve thư mục package `api/` trước file `api.py`. Tôi đã nhanh chóng nhận ra và chuyển sang chạy trực tiếp file `api.py` bằng Python làm script để uvicorn tự phân giải đối tượng `app` trong scope hiện tại.

---

## 7. Future Pitfalls (Cạm bẫy tương lai)
- **Thiếu kiểm tra tĩnh (Static Analysis)**: Lỗi NameError như thế này thường xảy ra khi viết code nhanh mà không chạy các công cụ linting hoặc type checking (`pyright`, `pylint`) trên toàn bộ module. Lần sau, trước khi commit hoặc build, chúng ta nên chạy linter hoặc khởi động thử backend để bắt các lỗi thiếu import cơ bản này.

---

## 8. Expert vs Beginner (Tư duy Chuyên gia vs Người mới)
- **Người mới**: Khi thấy lỗi "Failed to fetch", người mới có xu hướng tập trung sửa CORS ở frontend, thay đổi địa chỉ IP, tắt firewall, hoặc loay hoay cấu hình Next.js.
- **Chuyên gia**: Nhìn vào "Failed to fetch" và lập tức kiểm tra xem cổng `8003` có đang lắng nghe hay không, tiến trình Backend có tồn tại hay không, và tìm đến file log hệ thống để đọc traceback lỗi crash.

---

## 9. Transferable Lessons (Bài học rút ra)
- **Luôn ghi log chi tiết cho tiến trình con (Subprocess)**: Việc Electron ghi toàn bộ `stdout` và `stderr` của `api.exe` vào file `backend.log` là một thiết kế tuyệt vời. Nhờ có log này, mọi lỗi crash âm thầm của Python (kể cả lỗi syntax/import trước khi FastAPI kịp khởi chạy) đều được lưu lại chi tiết, giúp quá trình xử lý sự cố cực kỳ nhanh chóng.
