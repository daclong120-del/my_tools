# Lớp Người dùng và Đặc điểm (User Classes and Characteristics)

Tài liệu này phân loại các nhóm đối tượng sử dụng hệ thống **SocialPeta Downloader v2** và xác định các đặc điểm, yêu cầu kỹ thuật tương ứng của từng nhóm.

---

## 1. Phân loại Nhóm Người dùng (User Classes)

Hệ thống phục vụ 3 nhóm đối tượng người dùng chính trong môi trường doanh nghiệp quảng cáo (Ad Agency) hoặc nhà phát hành game/ứng dụng (Game Publisher):

```mermaid
graph TD
    classDef buyer fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef designer fill:#0f766e,stroke:#14b8a6,stroke-width:2px,color:#fff;
    classDef dev fill:#78350f,stroke:#d97706,stroke-width:2px,color:#fff;

    Buyer[1. Media Buyer / Ad Optimizer]:::buyer
    Designer[2. Designer / Video Editor]:::designer
    Dev[3. Developer / Administrator]:::dev
```

---

## 2. Đặc điểm Chi tiết từng Lớp Người dùng

### 2.1. Nhóm 1: Media Buyer / Người tối ưu hóa quảng cáo (Ad Optimizer)
* **Đặc điểm**:
  - Là người trực tiếp nghiên cứu đối thủ cạnh tranh trên SocialPeta để lên ý tưởng chiến dịch mới.
  - Cần thu thập nhanh chóng hàng loạt quảng cáo của một app/game cụ thể trong một khoảng thời gian ngắn để đánh giá xu hướng.
* **Yêu cầu đối với hệ thống**:
  - Tốc độ cào tải phải nhanh, giao diện đơn giản, dễ thao tác (chỉ cần chạy file `.bat` và chọn số thứ tự trên menu).
  - Không tải trùng lặp các quảng cáo cũ để tránh làm nhiễu dữ liệu phân tích xu hướng.
  - Đảm bảo thu thập được toàn bộ video (cả YouTube và CDN) của đối thủ.
* **Kỹ năng công nghệ**: Trung bình. Biết sử dụng máy tính văn phòng, trình duyệt web, và thao tác dòng lệnh cơ bản theo hướng dẫn có sẵn.

### 2.2. Nhóm 2: Nhà thiết kế đồ họa / Biên tập video (Designer / Video Editor)
* **Đặc điểm**:
  - Là người trực tiếp sử dụng các tài nguyên tải về (ảnh, video) để chỉnh sửa, thiết kế lại thành các mẫu quảng cáo mới (Creative Re-design).
  - Đòi hỏi chất lượng tài nguyên ở mức cao nhất để phục vụ dựng phim.
* **Yêu cầu đối với hệ thống**:
  - Tải video YouTube ở độ phân giải cao nhất (sử dụng tối đa sức mạnh của `yt-dlp`).
  - Ảnh tải về phải là ảnh gốc từ CDN, không bị nén hoặc lỗi định dạng.
  - Các tệp tin được phân loại gọn gàng theo thư mục tương ứng với từng mạng quảng cáo và tên ứng dụng để dễ tìm kiếm.
* **Kỹ năng công nghệ**: Trung bình. Sử dụng thành thạo các phần mềm đồ họa (Adobe Premiere, Photoshop, CapCut).

### 2.3. Nhóm 3: Nhà phát triển / Quản trị hệ thống (Developer / Admin)
* **Đặc điểm**:
  - Vận hành hệ thống tải tự động số lượng lớn (Bulk Download).
  - Thực hiện bảo trì mã nguồn, nâng cấp hệ thống khi giao diện SocialPeta thay đổi.
  - Theo dõi hiệu năng hệ thống và tài nguyên máy chủ/đường truyền.
* **Yêu cầu đối với hệ thống**:
  - Hệ thống ghi nhật ký hoạt động (logs) chi tiết để dễ khoanh vùng khi xảy ra lỗi.
  - Báo cáo kết quả lọc trùng cụ thể (`duplicate_audit.csv`) để kiểm toán dữ liệu.
  - Mã nguồn viết rõ ràng, dễ bảo trì, giải phóng bộ nhớ tốt (dọn dẹp thư mục tạm `.temp_download`).
* **Kỹ năng công nghệ**: Cao. Thành thạo lập trình Python, làm việc với Git, cơ sở dữ liệu SQLite và điều khiển tự động hóa Playwright.
