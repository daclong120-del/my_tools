# Yêu cầu Chức năng (Functional Requirements)

Tài liệu này đặc tả các yêu cầu chức năng (FR) chi tiết của hệ thống **SocialPeta Downloader v2**.

---

## 1. Danh sách Yêu cầu Chức năng chính

| Mã số | Tên yêu cầu | Mô tả chi tiết |
| :--- | :--- | :--- |
| **FR-01** | Kết nối CDP Chrome | Cho phép kết nối và điều khiển trình duyệt Google Chrome đang mở sẵn qua cổng debug (mặc định 9222). Hiển thị danh sách các tab đang hoạt động. |
| **FR-02** | Trích xuất Tên ứng dụng | Đọc tiêu đề tab Chrome để lấy tên app/nhà quảng cáo sạch. Nếu tiêu đề không chứa tên sạch, hệ thống quét DOM tìm class `.advertiser-name` hoặc `.app-title`. |
| **FR-03** | Bắt gói tin API mạng | Lắng nghe bất đồng bộ các gói tin phản hồi chứa cấu trúc mạng của SocialPeta (`/creative/list`). Giải nén dữ liệu JSON để lấy thông tin quảng cáo, ghi nhận đầy đủ 100% số lượng quảng cáo (60/60 items mỗi trang) vào cơ sở dữ liệu mà không được tự ý lọc trùng hay bỏ qua ở luồng cào này. |
| **FR-04** | Nhận diện & Click Youtube | Lọc ra các card quảng cáo có icon Youtube. Thuật toán Scoring Matcher bắt buộc phải kiểm tra sự hiện diện của icon YouTube trên card (không chấp nhận card không có icon YouTube) trước khi Playwright tự động cuộn màn hình đến vị trí card đó và click nút "Chi tiết" để mở modal thông tin, tránh click nhầm sang các mạng quảng cáo khác (như Admob) có cùng creative. |
| **FR-05** | Trích xuất link Youtube | Quét trong modal để trích xuất thẻ `iframe` Youtube (lấy `src`) hoặc thẻ `a` trỏ đến link Youtube thực tế, chuẩn hóa URL về dạng chuẩn. |
| **FR-06** | Phân trang tự động | Tự động click nút chuyển sang trang tiếp theo trên giao diện web từ trang 1 đến trang N theo cấu hình của người dùng. |
| **FR-07** | Kích hoạt mềm Soft Trigger | Nếu chuyển trang quá 30 giây không nhận được gói tin API, tự động cuộn màn hình lên/xuống và click nút Search trên web để ép tải lại API. |
| **FR-08** | Tải xuống đa luồng | Hỗ trợ nhiều worker chạy song song lấy link từ hàng đợi để tải. Ảnh/Video CDN tải bằng HTTP Client; Video Youtube tải bằng `yt-dlp`. |
| **FR-09** | Trì hoãn tải Video CDN | Toàn bộ video CDN được lưu tạm vào cơ sở dữ liệu SQLite dưới dạng trạng thái chờ (`pending`) và chỉ được truy vấn từ cơ sở dữ liệu để đưa vào hàng đợi tải xuống sau khi đã click cào xong toàn bộ link YouTube của trang đó. |
| **FR-10** | Lọc trùng lặp video 3 lớp | Kiểm tra chênh lệch thời lượng (`ffprobe`), kiểm tra mã MD5 của luồng âm thanh PCM trích xuất, và so sánh dHash hình ảnh Hamming trên 5 khung hình. Bộ lọc trùng lặp chỉ thực thi ở luồng tải xuống để quyết định có tải tệp hay không, tuyệt đối không được xóa/bỏ qua dữ liệu trong luồng cào thông tin. |
| **FR-11** | Báo cáo lọc trùng | Xuất báo cáo danh sách video bị lọc trùng sang file `duplicate_audit.csv` trong thư mục lưu trữ đích để người dùng tiện tra cứu. |
| **FR-12** | Bảng theo dõi trực tiếp | Dựng giao diện console cập nhật thời gian thực thông số: số tab, trang đang cào, số lượng ảnh/video đã cào, số lượng đã tải và số tệp trùng. |
| **FR-13** | Tự động phát hiện & Fallback thư mục | Tự động xác định thư mục `Downloads\SocialPeta_Downloader` của người dùng trên ổ đĩa `C:\` của Windows làm mặc định. Nếu người dùng cấu hình đường dẫn tới một ổ đĩa không hợp lệ/không tồn tại (ví dụ ổ `D:\` trên máy không có ổ `D:\`), hệ thống tự động fallback về thư mục trên ổ `C:\` và cập nhật lại cấu hình. |

---

## 2. Mô tả quy trình xử lý ngoại lệ (Exception Handling)

* **Lỗi click trượt card Youtube**:
  - Nếu click nút "Chi tiết" mà modal không mở ra sau 3 giây, hệ thống tự động đổi vị trí click hoặc cuộn lại card để thử lại, tránh gây đứng luồng.
* **Lỗi không tìm thấy link Youtube trong modal**:
  - Nếu modal mở ra nhưng quét DOM không thấy iframe hoặc link Youtube, hệ thống ghi nhận trạng thái quảng cáo đó là `failed`, đóng modal và xử lý ad tiếp theo.
* **Lỗi trùng lặp creative giữa các mạng quảng cáo (như Admob và YouTube)**:
  - Khi cùng một creative được triển khai trên cả Admob và YouTube, hệ thống bắt buộc phải kiểm tra và loại trừ các card không chứa icon YouTube (`net-icon-youtube`), chỉ cho phép click vào card có chứa icon YouTube để tránh mở sai modal của Admob.
* **Lỗi Database locked**:
  - Tích hợp khóa đồng bộ `history_lock` giữa luồng cào và luồng tải để bảo vệ các thao tác ghi dữ liệu SQLite, ngăn ngừa lỗi tranh chấp tài nguyên.


### 3.4. Hành vi xóa tệp trùng và Nguy cơ mất liên kết YouTube
* **Nguyên nhân**: Bộ lọc trùng lặp hoạt động theo cơ chế bất đồng bộ, tệp nào **tải xong trước** sẽ được lưu lại làm tệp gốc (Master File) và ghi vào `download_history`/`download_info.csv`. Tệp tải xong sau bị coi là trùng lặp (Duplicate) và bị xóa tệp thô khỏi đĩa, chỉ ghi nhận trạng thái trùng lặp vào `duplicate_audit.csv`.
* **Kịch bản lỗi giữ/xóa**:
  - **Trường hợp video YouTube tải xong trước**: Giữ video YouTube làm gốc, ghi thông tin kèm `youtube_url` vào `download_info.csv`. Video CDN tải xong sau bị xóa. (An toàn, giữ được link).
  - **Trường hợp video CDN (Admob) tải xong trước**: Giữ video CDN làm gốc (không chứa trường `youtube_url`). Video YouTube tải xong sau bị xác định là trùng lặp $\rightarrow$ **Xóa tệp YouTube**, bản ghi của YouTube bị đánh dấu trạng thái `duplicate` và **không được xuất** ra file `download_info.csv`. Kết quả là người dùng bị mất thông tin liên kết `youtube_url` trong báo cáo CSV sạch.
* **Tình trạng lưu trữ thực tế trong SQLite**: Liên kết YouTube và dữ liệu thô của quảng cáo YouTube bị trùng **không bị xóa mất hoàn toàn** khỏi hệ thống. Nó vẫn nằm trong bảng cơ sở dữ liệu `ad_metadata` ở SQLite với trạng thái `status = 'duplicate'`. Người dùng có thể truy vấn trực tiếp cơ sở dữ liệu để lấy lại nếu cần.
* **Khuyến nghị khắc phục thiết kế**:
  - **Ưu tiên giữ YouTube**: Thiết kế lại thứ tự ưu tiên của bộ lọc trùng lặp. Nếu phát hiện tệp mới trùng với tệp cũ, và tệp mới là YouTube (`youtube_video`) còn tệp cũ là CDN (`video`), hệ thống nên xóa tệp CDN cũ trên đĩa, thay thế nó bằng tệp YouTube mới, và cập nhật trường `youtube_url` cùng thông tin liên quan vào bản ghi gốc trong `download_history`.
  - **Cập nhật gộp thông tin (Info Merging)**: Nếu vẫn xóa tệp YouTube mới để giữ tệp CDN cũ, hệ thống bắt buộc phải thực hiện bước **gộp dữ liệu** — sao chép liên kết `youtube_url` từ bản ghi YouTube bị trùng cập nhật vào bản ghi CDN đang hoạt động trong bảng `download_history` để bảo toàn dữ liệu liên kết trên file báo cáo CSV.


