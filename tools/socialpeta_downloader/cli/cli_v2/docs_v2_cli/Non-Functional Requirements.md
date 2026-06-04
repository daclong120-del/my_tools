# Yêu cầu Phi chức năng (Non-Functional Requirements)

Tài liệu này đặc tả các yêu cầu phi chức năng (NFR), tiêu chuẩn chất lượng và ràng buộc vận hành của hệ thống **SocialPeta Downloader v2**.

---

## 1. Các Yêu cầu Phi chức năng chính

### 1.1. Hiệu năng và Tốc độ (Performance & Scalability)
* **Thời gian xử lý card Youtube**: Thời gian cho một luồng click cào mở modal, trích xuất link và đóng modal đối với mỗi card quảng cáo Youtube không được vượt quá **6 giây** trong điều kiện mạng ổn định.
* **Tải xuống song song**: Hệ thống phải hỗ trợ cấu hình số luồng tải song song từ **3 đến 8 luồng** (threads) mà không gây quá tải CPU hoặc làm nghẽn băng thông mạng cục bộ.
* **Thời gian đáp ứng giao diện**: Bảng theo dõi Rich Dashboard trên console phải cập nhật thông tin tiến độ cào tải định kỳ **1 giây một lần**.

### 1.2. Độ tin cậy và Tính ổn định (Reliability & Robustness)
* **Khả năng chạy bền bỉ**: Hệ thống có khả năng cào liên tục lên đến **100 trang** quảng cáo mà không bị tràn bộ nhớ (memory leak) hoặc crash luồng Playwright.
* **Khôi phục trạng thái lỗi**: Khi gặp lỗi mất mạng hoặc timeout từ API của SocialPeta, hệ thống không được dừng chương trình đột ngột mà phải thử lại qua cơ chế Soft Trigger tối đa 3 lần trước khi đánh dấu lỗi.
* **Bảo toàn dữ liệu**: Đảm bảo dọn dẹp sạch toàn bộ tệp tạm ở thư mục `.temp_download` khi kết thúc phiên chạy, kể cả khi người dùng nhấn phím ngắt tiến trình `Ctrl + C`.

### 1.3. Khả năng bảo trì và Khả năng đọc mã nguồn (Maintainability)
* **Cấu trúc mã nguồn**: Mã nguồn được chia tách rõ ràng theo mô hình hướng dịch vụ (Service-oriented design) với các module chuyên biệt:
  - `cli.py` đảm nhận giao diện người dùng.
  - `core.py` điều phối luồng chạy.
  - `sniffer.py` và `youtube.py` làm nhiệm vụ tự động hóa và cào quét.
  - `downloader.py` quản lý tải song song.
  - `deduplication.py` xử lý lọc trùng tệp tin.
* **Đồng bộ hóa dữ liệu tập trung**: Sử dụng SQLite làm bộ nhớ lưu trữ trạng thái tải giúp người dùng có thể tắt ứng dụng và chạy lại để tiếp tục tải tiếp từ trang bị ngắt quãng mà không cần tải lại từ đầu.

### 1.4. Tính tương thích (Compatibility)
* **Hệ điều hành**: Chạy ổn định trên hệ điều hành Microsoft Windows (Windows 10, Windows 11) thông qua môi trường Python 3.9+ hoặc tệp thực thi đóng gói.
* **Trình duyệt Google Chrome**: Tương thích tốt với phiên bản Google Chrome hiện hành hỗ trợ giao thức kết nối gán cổng gỡ lỗi CDP.

---

## 2. Ràng buộc Kỹ thuật hệ thống (System Constraints)

* **Yêu cầu cài đặt sẵn FFmpeg**: Hệ thống yêu cầu cài đặt sẵn công cụ dòng lệnh `ffmpeg` và `ffprobe` trong biến môi trường PATH của hệ điều hành Windows để phục vụ tiến trình lọc trùng lặp video.
* **Phụ thuộc yt-dlp**: Thư viện `yt-dlp` phải liên tục được cập nhật để tránh lỗi bị Google chặn hoặc hạn chế băng thông khi tải video trực tiếp từ YouTube.
