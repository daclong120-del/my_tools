# Mục tiêu Dự án (Project Objectives)

Tài liệu này xác định các mục tiêu cốt lõi và tiêu chí đánh giá thành công của hệ thống **SocialPeta Downloader v2**.

---

## 1. Mục tiêu Chiến lược (Strategic Goals)

* **Tự động hóa toàn diện quy trình thu thập quảng cáo**:
  - Loại bỏ hoàn toàn thao tác tải thủ công từng tệp ảnh hoặc video từ trang phân tích quảng cáo SocialPeta.
  - Tự động hóa chu trình: Kết nối tab trình duyệt Chrome $\rightarrow$ Quét gói tin mạng $\rightarrow$ Phân trang $\rightarrow$ Giả lập nhấp chuột cào link YouTube $\rightarrow$ Tải xuống tài nguyên $\rightarrow$ Lọc trùng lặp $\rightarrow$ Lưu trữ phân loại.

* **Đảm bảo tính trọn vẹn của tài nguyên (Asset Integrity)**:
  - Thu thập đầy đủ mọi loại tài nguyên quảng cáo bao gồm: ảnh tĩnh, ảnh thu nhỏ (thumbnails), video gốc CDN và đặc biệt là video YouTube nhúng (không bị sót link).
  - Tích hợp công cụ `yt-dlp` để tải video YouTube với chất lượng tốt nhất có thể thay vì các giải pháp quay màn hình hoặc tải chất lượng thấp.

* **Tối ưu hóa hiệu năng và băng thông**:
  - Sử dụng mô hình lập trình đa luồng (Multi-threading) để tải đồng thời nhiều tài nguyên cùng lúc, tận dụng tối đa băng thông đường truyền Internet của người dùng.
  - Thiết kế cơ chế hàng đợi xử lý bất đồng bộ để việc cào dữ liệu trên trình duyệt không bị tắc nghẽn bởi tốc độ tải xuống của ổ đĩa.

* **Tiết kiệm không gian lưu trữ (Storage Efficiency)**:
  - Tích hợp bộ lọc trùng lặp thông minh 3 lớp nhằm loại bỏ hoàn toàn các video giống hệt nhau hoặc chỉ khác nhau một chút về thông số kỹ thuật (độ phân giải, metadata, chênh lệch khung hình).
  - Giảm thiểu dung lượng ổ đĩa lưu trữ và loại bỏ các dữ liệu rác trước khi bàn giao cho đội ngũ thiết kế.

---

## 2. Tiêu chí Đánh giá Thành công (Success Criteria)

| Chỉ số đánh giá | Tiêu chí thành công |
| :--- | :--- |
| **Tỷ lệ thu thập YouTube** | Đạt **100%** số lượng video YouTube phát hiện trên trang (không bị bỏ sót do lỗi click trượt). |
| **Độ chính xác lọc trùng** | Nhận diện đúng **>98%** các video trùng lặp bằng thuật toán dHash hình ảnh và PCM Audio MD5. |
| **Tính ổn định của luồng** | Tự động khôi phục (qua Soft Trigger) khi trang web bị treo API hoặc mất kết nối tạm thời. |
| **Trải nghiệm người dùng** | Giao diện CLI hiển thị bảng tiến độ cập nhật trực quan mỗi giây, dễ thao tác qua menu số. |
| **An toàn tài nguyên** | Toàn bộ tệp tin tạm ở thư mục `.temp_download` được dọn dẹp sạch sẽ ngay sau khi hoàn tất tải. |
