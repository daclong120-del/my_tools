# Sơ đồ Hoạt động (Activity Diagram)

Tài liệu này đặc tả luồng hoạt động chi tiết (quy trình nghiệp vụ, các bước rẽ nhánh, xử lý song song và điều kiện quyết định) trong hệ thống **SocialPeta Downloader v2**.

Để xem sơ đồ dưới dạng hình vẽ trực quan, bạn hãy mở chế độ **Markdown Preview** trong trình soạn thảo (nhấn tổ hợp phím `Ctrl + Shift + V` hoặc click vào biểu tượng Preview ở góc trên cùng bên phải).

---

## 1. Hoạt động Khởi chạy & Cấu hình hệ thống (Khởi đầu)

Sơ đồ hoạt động mô tả quy trình người dùng khởi động ứng dụng và hệ thống thiết lập các tài nguyên ban đầu:

```mermaid
flowchart TD
    classDef start fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;

    Start([Khởi động run.bat]):::start --> ConnectCDP[Kết nối Chrome qua cổng debug 9222]:::process
    ConnectCDP --> CheckConnect{Kết nối thành công?}:::decision
    
    CheckConnect -- "Không" --> WarnUser[Hiển thị cảnh báo và hướng dẫn mở Chrome debug]:::process
    WarnUser --> ConnectCDP
    
    CheckConnect -- "Có" --> DetectTabs[Quét danh sách Tab SocialPeta đang mở]:::process
    DetectTabs --> ShowMenu[Hiển thị Menu CLI cho người dùng lựa chọn]:::process
    
    ShowMenu --> UserInput[1. Chọn Tab cần tải<br>2. Nhập số trang cần cào<br>3. Chọn thư mục lưu]:::process
    UserInput --> SelectMode{Chọn chế độ tải}:::decision
    
    SelectMode -- "Tải tất cả (Tải full)" --> InitSystem[Khởi tạo SQLite DB, thư mục tạm .temp_download & hàng đợi Queue]:::process
    
    InitSystem --> ForkProcess[Rẽ nhánh chạy song song: Luồng cào Scraper & Luồng Downloader]:::process
```

---

## 2. Hoạt động Cào quét, Phân trang & Trích xuất Youtube (Luồng Cào)

Mô tả hoạt động chi tiết của **Luồng Cào dữ liệu (Scraper Thread)** khi điều khiển trình duyệt và xử lý cào link Youtube:

```mermaid
flowchart TD
    classDef start fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef merge fill:#7c3aed,stroke:#5b21b6,stroke-width:2px,color:#fff;

    StartCrawl([Bắt đầu quét trang]):::start --> ScrollPage[Cuộn trang web xuống cuối để kích hoạt API]:::process
    ScrollPage --> SniffAPI[Lắng nghe & Bắt gói tin API creative/list]:::process
    
    SniffAPI --> CheckDB{ad_id đã tồn tại trong SQLite?}:::decision
    CheckDB -- "Đã tồn tại" --> SkipItem[Bỏ qua quảng cáo]:::process
    
    CheckDB -- "Chưa tồn tại" --> UpgradeYT{Phát hiện icon/chữ Youtube trên DOM?}:::decision
    
    UpgradeYT -- "Có" --> MarkYT[Nâng cấp media_type = youtube_click_required<br>Đẩy vào Hàng đợi xử lý Youtube]:::process
    UpgradeYT -- "Không (Video CDN)" --> DeferCDN[Lưu thông tin vào SQLite<br>status = pending, media_type = video<br>Trì hoãn chưa tải]:::process
    
    SkipItem --> NextAd{Còn ad nào trong trang?}:::decision
    MarkYT --> NextAd
    DeferCDN --> NextAd
    
    NextAd -- "Còn" --> CheckDB
    
    NextAd -- "Hết" --> ProcessYTQueue[Bắt đầu xử lý hàng đợi click Youtube của trang]:::process
    
    ProcessYTQueue --> ClickCard[Playwright cuộn tới card & click Chi tiết]:::process
    ClickCard --> PollYoutubeLink[Quét modal tìm link Youtube trong 3 giây]:::process
    
    PollYoutubeLink --> FoundYT{Tìm thấy link Youtube?}:::decision
    FoundYT -- "Có" --> SaveYT[Đổi loại thành youtube_video & đẩy vào hàng đợi tải xuống]:::process
    FoundYT -- "Không" --> MarkFail[Đánh dấu ad_id là failed]:::process
    
    SaveYT --> CloseModal[Nhấn ESC đóng modal chi tiết]:::process
    MarkFail --> CloseModal
    
    CloseModal --> MoreYT{Còn card Youtube cần click?}:::decision
    MoreYT -- "Còn" --> ClickCard
    
    MoreYT -- "Hết" --> ReleaseCDN[Truy vấn video CDN pending từ SQLite<br>Đẩy vào hàng đợi tải xuống]:::process
    
    ReleaseCDN --> NextPage{Đã cào đủ số trang cấu hình?}:::decision
    NextPage -- "Chưa đủ" --> ClickNextPage[Click nút chuyển sang trang tiếp theo]:::process
    ClickNextPage --> CheckTimeout{Quá 30s không nhận được API?}:::decision
    
    CheckTimeout -- "Có (Bị treo)" --> SoftTrigger[Kích hoạt Soft Trigger: Cuộn trang & Click nút Tìm kiếm]:::process
    SoftTrigger --> ScrollPage
    CheckTimeout -- "Không" --> ScrollPage
    
    NextPage -- "Đã đủ" --> EndCrawl([Hoàn tất cào quét trang]):::start
```

---

## 3. Hoạt động Tải xuống & Lọc trùng lặp (Luồng Tải)

Mô tả các hoạt động của **Luồng tải xuống (Downloader Workers)** và quy trình kiểm duyệt lọc trùng lặp 3 lớp:

```mermaid
flowchart TD
    classDef start fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef decision fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;

    StartDL([Lấy tệp tin từ hàng đợi tải xuống]):::start --> DownloadTemp[Tải file về thư mục tạm .temp_download]:::process
    DownloadTemp --> CheckType{Là Ảnh hay Video?}:::decision
    
    %% Phân luồng Ảnh
    CheckType -- "Ảnh" --> CheckMD5Img{Mã MD5 trùng với ảnh đã có?}:::decision
    CheckMD5Img -- "Trùng" --> DeleteTempImg[Xóa file ảnh tạm]:::process
    CheckMD5Img -- "Mới" --> MoveImg[Di chuyển ảnh vào thư mục đích & Cập nhật SQLite = Done]:::process
    
    %% Phân luồng Video
    CheckType -- "Video" --> Step1{Lớp 1: Khác thời lượng video bằng ffprobe > 0.05s?}:::decision
    
    Step1 -- "Khác (Video mới)" --> MoveVid[Di chuyển video vào thư mục đích & Cập nhật SQLite = Done]:::process
    Step1 -- "Bằng nhau" --> Step2[Lớp 2: Trích xuất PCM audio & so sánh mã MD5 âm thanh]:::process
    
    Step2 --> CheckAudio{Mã MD5 âm thanh trùng?}:::decision
    CheckAudio -- "Không trùng" --> MoveVid
    CheckAudio -- "Trùng" --> Step3[Lớp 3: Trích xuất 5 khung hình đặc trưng & tính dHash]:::process
    
    Step3 --> CheckHash{Khoảng cách Hamming <= 13 trên ít nhất 4/5 khung hình?}:::decision
    CheckHash -- "Không trùng" --> MoveVid
    CheckHash -- "Trùng (Trùng lặp)" --> DeleteTempVid[Xóa video tạm & Ghi log audit duplicate_audit.csv]:::process
    
    MoveImg --> EndDL([Hoàn thành một lượt tải]):::start
    DeleteTempImg --> EndDL
    MoveVid --> EndDL
    DeleteTempVid --> EndDL
```
