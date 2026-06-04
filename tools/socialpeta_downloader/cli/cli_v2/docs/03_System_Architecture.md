# Kiến trúc Hệ thống và Dữ liệu (System Architecture)

Tài liệu này mô tả cấu trúc các lớp (Layers), cơ chế 3 luồng chạy song song và thiết kế cơ sở dữ liệu SQLite giúp quản lý đồng bộ.

---

## 1. Mô tả vai trò các thành phần chính (Layers)

* **Lớp Giao diện (Presentation Layer) - `cli.py`**:
  - Cung cấp Menu In-memory bằng `InquirerPy`.
  - Hiển thị bảng Live Dashboard thống kê tiến trình bằng thư viện `rich`.

* **Lớp Điều khiển (Core Layer) - `core.py`**:
  - Đóng vai trò bộ não điều phối chính. Khởi tạo DB SQLite, quản lý trạng thái (`threading.Event`, `Queue`).
  - **Luôn khởi chạy cả 3 luồng** (Scraper, Downloader, Deduplicator) không phụ thuộc vào `download_mode`. Việc rẽ nhánh xử lý được thực hiện qua việc điều phối Filter Queue và phân loại gói tin tại Sniffer.

* **Lớp Tự động hóa & Cào quét (Browser Layer)**:
  - **`tab_manager.py`**: Kết nối Chrome debug bằng CDP. Nhận diện tên app từ HTML title/DOM để tạo thư mục lưu.
  - **`sniffer.py`**: Lắng nghe gói tin API `/creative/list`. Phân loại tài nguyên. **Áp dụng bộ lọc `download_mode`** ngay tại đây: nếu chọn "Chỉ tải ảnh", nó sẽ từ chối ghi dữ liệu Video vào Database, dẫn đến việc luồng `youtube.py` dù có quét DOM thấy icon YouTube cũng không có dữ liệu đối chiếu để đưa vào hàng đợi Click (tránh click thừa).
  - **`youtube.py`**: Chứa thuật toán khớp điểm (**Scoring Matcher**) lọc cứng bằng `.net-icon-youtube`. Tự động tìm `href` hoặc `iframe src` YouTube trong modal chi tiết.

* **Lớp Tải xuống song song (Download Layer) - `downloader.py`**:
  - Pool gồm nhiều worker thread. Với Ảnh, nó check MD5 trực tiếp ngay trên thread và lưu file. Với Video, nó gọi `yt-dlp` hoặc tải `requests`, lưu vào `.temp_download` rồi **đẩy thông tin vào `filter_queue`** cho luồng Dedup xử lý. Nếu chạy chế độ tải Ảnh, `filter_queue` sẽ hoàn toàn rỗng.

* **Lớp Lọc trùng & Dữ liệu (Data Layer) - `deduplication.py` & `session.py`**:
  - Chạy ngầm liên tục (Idle Listening) trên `filter_queue`. Lọc trùng video qua 3 bước khắt khe bằng FFmpeg (Thời lượng -> Mã âm thanh PCM -> dHash 5 khung hình). Tự động dọn dẹp file `.temp_download`.

---

## 2. Thiết kế Cơ sở dữ liệu (Database Design)

Ứng dụng dùng SQLite (tệp `ad_metadata.db`) làm Single Source of Truth cho trạng thái tải và chống click trùng lặp.

### Cấu trúc bảng `ad_metadata`
```sql
CREATE TABLE IF NOT EXISTS ad_metadata (
    ad_id TEXT PRIMARY KEY,
    media_type TEXT,
    status TEXT,
    fpath TEXT,
    item_json TEXT,
    youtube_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
* **`media_type`**: `image`, `video` (CDN), `youtube_click_required` (đã cào API, chờ click Playwright), `youtube_video` (đã lấy link yt chuẩn).
* **`status`**: `pending` (chờ tải), `downloading`, `done`, hoặc `failed`.

### Khóa đồng bộ luồng (Concurrency Control)
Vì hệ thống chạy mô hình đa luồng (1 Scraper ghi + N Downloader đọc/ghi), việc tránh lỗi `database is locked` được xử lý bằng:
1. **Khóa `history_lock`**: Bọc toàn bộ truy vấn `SELECT/INSERT/UPDATE` bằng `with self.context.history_lock:`.
2. Mỗi luồng tự mở một connection SQLite cục bộ, không dùng chung biến `conn`.
3. Commit `conn.commit()` ngay lập tức để nhả khóa ghi tức thì.
