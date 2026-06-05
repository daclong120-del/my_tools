# Đặc tả kỹ thuật cho CLI mới (Unified CLI Specification)

Tài liệu này đặc tả chi tiết giao diện dòng lệnh mới (CLI) thống nhất cho dự án **SocialPeta Downloader**, gộp toàn bộ các script đơn lẻ trong thư mục `modules/` thành một công cụ dòng lệnh duy nhất, dễ bảo trì và dễ sử dụng.

---

## 1. Thiết kế tổng quan
CLI mới sẽ được triển khai bằng thư viện tiêu chuẩn `argparse` của Python để tránh phát sinh thêm dependency bên ngoài và chạy nhanh nhất có thể.

Tên script: `scripts/new_cli.py` (hoặc sẽ thay thế trực tiếp vào `scripts/cli.py` khi người dùng yêu cầu).

Cú pháp gọi lệnh:
```bash
python scripts/new_cli.py <subcommand> [options]
```

---

## 2. Danh sách các Subcommand & Tham số

### 2.1. `start-chrome` (Khởi chạy Chrome)
* **Mô tả:** Khởi động Google Chrome với cổng remote debugging (mặc định: `9222`) và profile độc lập.
* **Tham số:**
  * `--port`, `-p` (int, mặc định: `9222`): Cổng debug của Chrome.
  * `--profile-dir` (str, tùy chọn): Thư mục lưu profile Chrome debug.

### 2.2. `list-tabs` (Liệt kê Tab)
* **Mô tả:** Quét và liệt kê tất cả các tab SocialPeta đang hoạt động trên cổng debug của Chrome.
* **Tham số:**
  * `--port`, `-p` (int, mặc định: `9222`): Cổng debug của Chrome để quét.

### 2.3. `connect-tab` (Kiểm tra kết nối Tab)
* **Mô tả:** Kết nối thử tới tab SocialPeta đang hoạt động (hoặc tab đầu tiên) để kiểm tra giao thức CDP.
* **Tham số:**
  * `--port`, `-p` (int, mặc định: `9222`): Cổng debug của Chrome.
  * `--mode` (str, mặc định: `current`, lựa chọn: `current`, `first`): Chọn kết nối tới tab đang hiển thị (`current`) hoặc tab SocialPeta đầu tiên tìm thấy (`first`).

### 2.4. `scrape` (Cào dữ liệu)
* **Mô tả:** Cào thông tin quảng cáo trên tab hiện tại và lưu vào file CSV.
* **Tham số:**
  * `--port`, `-p` (int, mặc định: `9222`): Cổng debug của Chrome.
  * `--pages`, `-n` (int, mặc định: `1`): Số lượng trang cần cào.
  * `--mode` (str, mặc định: `all`, lựa chọn: `all`, `youtube`): Chỉ cào YouTube hay cào tất cả quảng cáo.
  * `--csv-path` (str, tùy chọn): Đường dẫn file CSV đầu ra (mặc định lưu vào `modules/scraped_creatives.csv`).

### 2.5. `download` (Tải tài nguyên)
* **Mô tả:** Tải ảnh/video từ file CSV đã cào về máy.
* **Tham số:**
  * `--csv-path` (str, bắt buộc): Đường dẫn file CSV chứa danh sách quảng cáo cần tải.
  * `--output-dir` (str, tùy chọn): Thư mục lưu file tải về.
  * `--mode` (str, mặc định: `all`, lựa chọn: `all`, `image`, `youtube`, `cdn-video`): Chế độ lọc tải tài nguyên.
  * `--threads`, `-t` (int, mặc định: `3`): Số luồng tải video song song.

### 2.6. `fill-names` (Điền tên file thiếu)
* **Mô tả:** Điền các tên file `video_name` còn thiếu trong file CSV chỉ định sử dụng logic đặt tên duy nhất của core engine.
* **Tham số:**
  * `--csv-path` (str, bắt buộc): Đường dẫn file CSV cần cập nhật.

### 2.7. `crawl` (Cào và tải tự động - Full Flow)
* **Mô tả:** Chạy quy trình tự động hóa hoàn chỉnh (phân trang, bắt gói tin, trích xuất YouTube và tải về) trên tất cả active tabs.
* **Tham số:**
  * `--pages`, `-n` (int, mặc định: `10`): Số lượng trang muốn cào trên mỗi tab.
  * `--threads`, `-t` (int, mặc định: `5`): Số luồng tải video song song.
  * `--dir`, `-d` (str, tùy chọn): Thư mục lưu kết quả tải về.

### 2.8. `clear` (Dọn dẹp phiên)
* **Mô tả:** Dọn dẹp dữ liệu phiên cũ (SQLite database, file tạm JSON, file download dở dang).
* **Tham số:**
  * `--keep-history` (action="store_true"): Nếu bật flag này, sẽ giữ lại bảng lịch sử đã tải thành công, chỉ dọn các file tạm.

---

## 3. Bản kế hoạch triển khai
1. **Thảo luận & Thống nhất đặc tả:** Xác nhận giao diện dòng lệnh trên đáp ứng đủ yêu cầu của bạn chưa.
2. **Triển khai code CLI:** Tạo file `scripts/new_cli.py` với cấu trúc `argparse` và ánh xạ các subcommand vào các hàm tương ứng của lớp `SocialPetaDownloaderCore`, `TabScanner`, `ChromeService`, v.v.
3. **Kiểm thử CLI:** Chạy thử các lệnh để đảm bảo hoạt động trơn tru.
