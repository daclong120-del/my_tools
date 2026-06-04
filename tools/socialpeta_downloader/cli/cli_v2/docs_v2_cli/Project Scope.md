# Phạm vi Dự án (Project Scope)

Tài liệu này xác định ranh giới hoạt động của hệ thống **SocialPeta Downloader v2**, phân định rõ những phần việc nằm trong phạm vi (In-Scope) và nằm ngoài phạm vi (Out-of-Scope) phát triển.

---

## 1. Nằm trong Phạm vi (In-Scope)

### 1.1. Tự động hóa và Cào quét mạng (Browser Automation & Sniffing)
* **Kết nối CDP Chrome**: Chỉ kết nối và điều khiển trình duyệt Google Chrome đang mở sẵn ở chế độ Debug trên cổng chỉ định (mặc định `9222`).
* **Bắt gói tin API**: Đón bắt gói tin `/creative/list` hoặc `/creative-rank/list` để trích xuất danh sách quảng cáo.
* **Phân trang tự động**: Click nút phân trang từ trang `1` đến trang `N` dựa trên số trang người dùng nhập ở Menu cấu hình.
* **Cơ chế Soft Trigger**: Cuộn trang lên xuống và tự click nút "Tìm kiếm" (Search) để kích thích tải lại dữ liệu khi xảy ra hiện tượng treo API.

### 1.2. Giả lập hành vi lấy link YouTube thực
* **Thuật toán Scoring Matcher**: Tính điểm dựa trên so khớp ảnh thu nhỏ (thumbnail), tên ứng dụng (App Name) và nội dung chữ (Title/Body) để click chính xác vào nút "Chi tiết" của card quảng cáo cần lấy link YouTube.
* **Trích xuất link gốc**: Điều khiển Playwright mở modal chi tiết quảng cáo, quét tìm thẻ `iframe` phát video hoặc thẻ `a` trỏ đến liên kết YouTube thực tế.
* **Đóng modal tự động**: Gửi phím `Escape` để đóng modal sau khi cào thành công để tiếp tục xử lý các card khác.
* **Cơ chế chống click trùng**: Lưu trạng thái trong SQLite và đổi loại tài nguyên để không bao giờ click lại cùng một quảng cáo YouTube 2 lần.

### 1.3. Tải xuống đa luồng và Lọc trùng lặp
* **Tải xuống song song**: Tải ảnh và video CDN bằng HTTP Client; tải video YouTube bằng `yt-dlp`.
* **Trì hoãn tải CDN**: Toàn bộ video gốc CDN được lưu tạm trạng thái vào cơ sở dữ liệu SQLite và chỉ truy vấn từ SQLite để đưa vào hàng đợi tải sau khi đã click cào xong toàn bộ link YouTube của trang đó.
* **Bộ lọc trùng lặp 3 lớp**:
  - So sánh thời lượng video (`ffprobe`).
  - So sánh mã hóa MD5 của luồng âm thanh PCM (`ffmpeg`).
  - So sánh khoảng cách Hamming (`dHash`) và độ sáng trên 5 khung hình đặc trưng (`ffmpeg`).
* **Quản lý tệp tin sạch**: Di chuyển file độc nhất vào thư mục đích của người dùng, đổi tên theo chuẩn `ad_id`, tự động dọn dẹp thư mục tạm `.temp_download` và ghi nhật ký lọc trùng `duplicate_audit.csv`.

---

## 2. Nằm ngoài Phạm vi (Out-of-Scope)

* **Tự động vượt CAPTCHA**: Hệ thống **không** tích hợp các giải pháp giải mã CAPTCHA tự động (như 2Captcha, Anti-Captcha). Nếu trang web SocialPeta yêu cầu xác thực người máy, người dùng bắt buộc phải tự tay giải CAPTCHA trực tiếp trên trình duyệt Chrome debug đang mở.
* **Hỗ trợ các trình duyệt khác**: Hệ thống không hỗ trợ điều khiển Firefox, Safari hay Microsoft Edge. Chỉ hoạt động tối ưu nhất trên Google Chrome qua cổng debug CDP.
* **Hỗ trợ các nền tảng khác ngoài SocialPeta**: Hệ thống được thiết kế đặc thù cho cấu trúc gói tin API và DOM của SocialPeta. Không hỗ trợ tải quảng cáo từ BigSpy, AdSpy hay các nền tảng phân tích khác.
* **Cài đặt dependencies hệ thống**: Hệ thống không tự động cài đặt `FFmpeg` hoặc `Python` lên máy tính của người dùng. Người dùng phải tự cài đặt các phụ thuộc hệ thống này trước khi khởi chạy công cụ.
