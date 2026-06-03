# Yêu cầu Chức năng (Functional Requirements)

Tài liệu này đặc tả các yêu cầu chức năng (FR) chi tiết của hệ thống **SocialPeta Downloader v2**.

---

## 1. Danh sách Yêu cầu Chức năng chính

| Mã số | Tên yêu cầu | Mô tả chi tiết |
| :--- | :--- | :--- |
| **FR-01** | Kết nối CDP Chrome | Cho phép kết nối và điều khiển trình duyệt Google Chrome đang mở sẵn qua cổng debug (mặc định 9222). Hiển thị danh sách các tab đang hoạt động. |
| **FR-02** | Trích xuất Tên ứng dụng | Đọc tiêu đề tab Chrome để lấy tên app/nhà quảng cáo sạch. Nếu tiêu đề không chứa tên sạch, hệ thống quét DOM tìm class `.advertiser-name` hoặc `.app-title`. |
| **FR-03** | Bắt gói tin API mạng | Lắng nghe bất đồng bộ các gói tin phản hồi chứa cấu trúc mạng của SocialPeta (creative/list). Giải nén dữ liệu JSON để lấy thông tin quảng cáo. |
| **FR-04** | Nhận diện & Click Youtube | Lọc ra các card quảng cáo có icon Youtube. Playwright tự động cuộn màn hình đến vị trí card đó và click nút "Chi tiết" để mở modal thông tin. |
| **FR-05** | Trích xuất link Youtube | Quét trong modal để trích xuất thẻ `iframe` Youtube (lấy `src`) hoặc thẻ `a` trỏ đến link Youtube thực tế, chuẩn hóa URL về dạng chuẩn. |
| **FR-06** | Phân trang tự động | Tự động click nút chuyển sang trang tiếp theo trên giao diện web từ trang 1 đến trang N theo cấu hình của người dùng. |
| **FR-07** | Kích hoạt mềm Soft Trigger | Nếu chuyển trang quá 30 giây không nhận được gói tin API, tự động cuộn màn hình lên/xuống và click nút Search trên web để ép tải lại API. |
| **FR-08** | Tải xuống đa luồng | Hỗ trợ nhiều worker chạy song song lấy link từ hàng đợi để tải. Ảnh/Video CDN tải bằng HTTP Client; Video Youtube tải bằng `yt-dlp`. |
| **FR-09** | Trì hoãn tải Video CDN | Toàn bộ video CDN được lưu tạm vào tệp JSON và chỉ đưa vào hàng đợi tải xuống sau khi đã click cào xong toàn bộ link YouTube của trang đó. |
| **FR-10** | Lọc trùng lặp video 3 lớp | Kiểm tra chênh lệch thời lượng (`ffprobe`), kiểm tra mã MD5 của luồng âm thanh PCM trích xuất, và so sánh dHash hình ảnh Hamming trên 5 khung hình. |
| **FR-11** | Báo cáo lọc trùng | Xuất báo cáo danh sách video bị lọc trùng sang file `duplicate_audit.csv` trong thư mục lưu trữ đích để người dùng tiện tra cứu. |
| **FR-12** | Bảng theo dõi trực tiếp | Dựng giao diện console cập nhật thời gian thực thông số: số tab, trang đang cào, số lượng ảnh/video đã cào, số lượng đã tải và số tệp trùng. |

---

## 2. Mô tả quy trình xử lý ngoại lệ (Exception Handling)

* **Lỗi click trượt card Youtube**:
  - Nếu click nút "Chi tiết" mà modal không mở ra sau 3 giây, hệ thống tự động đổi vị trí click hoặc cuộn lại card để thử lại, tránh gây đứng luồng.
* **Lỗi không tìm thấy link Youtube trong modal**:
  - Nếu modal mở ra nhưng quét DOM không thấy iframe hoặc link Youtube, hệ thống ghi nhận trạng thái quảng cáo đó là `failed`, đóng modal và xử lý ad tiếp theo.
* **Lỗi Database locked**:
  - Tích hợp khóa đồng bộ `history_lock` giữa luồng cào và luồng tải để bảo vệ các thao tác ghi dữ liệu SQLite, ngăn ngừa lỗi tranh chấp tài nguyên.
