# Sơ đồ Kiến trúc Hệ thống (Architecture Diagram)

Tài liệu này mô tả kiến trúc phân lớp, các thành phần phần mềm và luồng trao đổi dữ liệu trong hệ thống **SocialPeta Downloader v2**.

Để xem sơ đồ dưới dạng hình vẽ trực quan, bạn hãy mở chế độ **Markdown Preview** trong trình soạn thảo (nhấn tổ hợp phím `Ctrl + Shift + V` hoặc click vào biểu tượng Preview ở góc trên cùng bên phải).

---

## 1. Sơ đồ Kiến trúc Phân lớp (Layered Architecture)

Dưới đây là sơ đồ kiến trúc thể hiện cách các thành phần trong code được chia lớp và giao tiếp với nhau:

```mermaid
graph TD
    %% Định nghĩa Màu sắc hiển thị cho từng lớp kiến trúc
    classDef ui fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef core fill:#581c87,stroke:#a855f7,stroke-width:2px,color:#fff;
    classDef browser fill:#0f766e,stroke:#14b8a6,stroke-width:2px,color:#fff;
    classDef downloader fill:#78350f,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef db fill:#065f46,stroke:#10b981,stroke-width:2px,color:#fff;

    %% Lớp Giao diện (Presentation Layer)
    subgraph LayerUI ["1. LỚP GIAO DIỆN (UI/CLI LAYER)"]
        CLI[cli.py: Console Menu & Rich Live Dashboard]:::ui
    end

    %% Lớp Điều khiển (Core / Orchestration Layer)
    subgraph LayerCore ["2. LỚP ĐIỀU KHIỂN TRUNG TÂM (CORE LAYER)"]
        CoreEngine[core.py: Quản lý luồng chạy & Đồng bộ trạng thái Context]:::core
    end

    %% Lớp Tự động hóa Trình duyệt (Browser Automation & Sniffing Layer)
    subgraph LayerBrowser ["3. LỚP TỰ ĐỘNG HÓA VÀ CÀO QUÉT (BROWSER LAYER)"]
        TabMgr[tab_manager.py: Quản lý kết nối CDP Chrome & Trích xuất tên App từ DOM]:::browser
        Sniffer[sniffer.py: Bắt gói tin API, Phân trang & Soft Trigger]:::browser
        YTService[youtube.py: Thuật toán Scoring Matcher, Click Chi tiết & Cào Youtube]:::browser
    end

    %% Lớp Tải xuống song song (Parallel Downloader Layer)
    subgraph LayerDownloader ["4. LỚP TẢI XUỐNG VÀ XỬ LÝ TỆP (DOWNLOAD LAYER)"]
        Downloader[downloader.py: Quản lý các luồng tải song song]:::downloader
        YTDLP[Thư viện yt-dlp: Tải video Youtube chất lượng cao]:::downloader
        HTTPClient[HTTP Client: Tải ảnh tĩnh và video CDN gốc]:::downloader
    end

    %% Lớp Lọc trùng & Cơ sở dữ liệu (Deduplication & Data Layer)
    subgraph LayerData ["5. LỚP LỌC TRÙNG VÀ DỮ LIỆU (DATA LAYER)"]
        Dedup[deduplication.py: Lọc trùng video 3 lớp <Duration - PCM Audio MD5 - Frame dHash>]:::db
        SQLiteDB[(SQLite DB: ad_metadata.db)]:::db
        FileStore[(Thư mục lưu trữ kết quả & Folder tạm .temp_download)]:::db
    end

    %% Các luồng giao tiếp chính giữa các lớp
    CLI -->|1. Cấu hình & Chạy| CoreEngine
    CoreEngine -->|2. Khởi tạo & Điều khiển| TabMgr
    CoreEngine -->|3. Đẩy file vào hàng đợi| Downloader
    
    TabMgr -->|CDP Hook| Sniffer
    Sniffer -->|Nâng cấp Youtube| YTService
    
    YTService -->|4. Lưu trạng thái & Ghi nhận| SQLiteDB
    Sniffer -->|Trì hoãn lưu JSON tạm| FileStore
    
    Downloader -->|Gọi tải| YTDLP
    Downloader -->|Gọi tải| HTTPClient
    Downloader -->|5. Yêu cầu lọc trùng| Dedup
    
    Dedup -->|So sánh lịch sử & Lưu file sạch| FileStore
    Dedup -->|Truy vấn & Cập nhật trạng thái| SQLiteDB
    CLI -.->|Đọc trạng thái hiển thị| SQLiteDB
```

---

## 2. Mô tả vai trò các thành phần chính

### 2.1. Lớp Giao diện (Presentation Layer)
* **`cli.py`**:
  - Cung cấp menu tương tác đầu vào để người dùng cấu hình tham số tải.
  - Sử dụng thư viện `rich` để dựng giao diện bảng biểu trực quan hiển thị trạng thái cào tải theo thời gian thực (Ads sniffed, Pending, Done, Duplicates, Speed).

### 2.2. Lớp Điều khiển (Core Layer)
* **`core.py`**:
  - Đóng vai trò là bộ não điều phối chính. Khởi tạo cơ sở dữ liệu SQLite, khởi chạy các luồng tải song song (`downloader_threads`), luồng lọc trùng video (`dedup_thread`), và bắt đầu luồng cào dữ liệu Playwright trên từng tab.
  - Quản lý cơ chế đồng bộ trạng thái luồng (`threading.Event`, `Queue`).

### 2.3. Lớp Tự động hóa và Cào quét (Browser Layer)
* **`tab_manager.py`**: Kết nối tới trình duyệt Chrome qua cổng debug bằng giao thức CDP (Chrome DevTools Protocol). Trích xuất tên game/ứng dụng để tự tạo thư mục lưu.
* **`sniffer.py`**: Lắng nghe sự kiện gói tin phản hồi mạng. Khi nhận thấy gói tin `/creative/list`, tiến hành phân tách tài nguyên. Điều khiển phân trang tự động và thực hiện cơ chế kích hoạt lại (Soft Trigger) khi trang web bị đứng.
* **`youtube.py`**: Chứa thuật toán khớp điểm (**Scoring Matcher**) để tìm đúng card quảng cáo YouTube cần click, ra lệnh cho trình duyệt click mở modal chi tiết, trích xuất link YouTube gốc và đóng modal.

### 2.4. Lớp Tải xuống song song (Download Layer)
* **`downloader.py`**: Lấy các tệp tin từ hàng đợi tải xuống (`pending_downloads`). Tự động nhận diện loại tệp tin để phân phối: gọi `yt-dlp` đối với link YouTube, hoặc gọi tải HTTP thông thường đối với ảnh và video gốc CDN. Lưu trữ tạm thời vào thư mục ẩn `.temp_download`.

### 2.5. Lớp Lọc trùng và Dữ liệu (Data Layer)
* **`deduplication.py`**: Đảm nhiệm vai trò lọc trùng lặp video bằng quy trình 3 lớp nghiêm ngặt (kiểm tra độ dài, mã MD5 âm thanh PCM trích xuất bằng `ffmpeg`, và khoảng cách Hamming `dHash` của các khung hình đặc trưng).
* **SQLite Database (`ad_metadata`)**: Lưu trữ và khóa trạng thái xử lý của từng quảng cáo theo `ad_id` để tránh việc xử lý hoặc click trùng lặp.
* **File Store**: Tổ chức thư mục lưu trữ đích sạch sẽ, tự động dọn dẹp thư mục tạm `.temp_download` khi hoàn tất.
