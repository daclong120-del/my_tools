# Sơ đồ Luồng và Trình tự (Workflows & Diagrams)

Tài liệu này mô tả chi tiết các sơ đồ hoạt động, luồng xử lý và cách hệ thống rẽ nhánh khi người dùng thay đổi chế độ tải (Đặc tả cách xử lý riêng cho 3 Use Case: Tải tất cả, Chỉ tải ảnh, Chỉ tải YouTube).

---

## 1. Lưu đồ Hoạt động (Flowchart)

Lưu đồ thể hiện cách hệ thống rẽ nhánh logic và tối ưu luồng dựa trên lựa chọn của người dùng, đặc biệt ở khâu Cào Dữ Liệu và Lọc Trùng.

```mermaid
flowchart TD
    classDef menu fill:#2b3a4a,stroke:#3b82f6,color:#fff;
    classDef process fill:#1e293b,stroke:#a855f7,color:#fff;
    classDef storage fill:#0f172a,stroke:#10b981,color:#fff;

    BatDau([Khởi chạy CLI]) --> ChonTab[Chọn Tab Chrome & Chế độ tải]:::menu
    
    ChonTab --> UC1["1. Tải tất cả"]:::menu
    ChonTab --> UC2["2. Chỉ tải ảnh"]:::menu
    ChonTab --> UC3["3. Chỉ tải YouTube"]:::menu

    %% Rẽ nhánh thiết lập các luồng (Code thực tế luôn khởi chạy 3 luồng, nhưng điều tiết qua Filter Queue)
    UC1 --> SetupFull[Sniffer nhận mọi gói tin + Downloader xử lý Video & Ảnh + Đẩy Video sang FFmpeg Dedup]:::process
    UC2 --> SetupAnh[Sniffer CHỈ nhận Ảnh + Bỏ qua lưu Video vào DB -> Hàng đợi Click YT trống -> Dedup Idle]:::process
    UC3 --> SetupYT[Sniffer CHỈ nhận link YT + Bỏ qua lưu Ảnh/CDN -> Chỉ xử lý YT_Click]:::process

    SetupFull --> KhoiDong[Tiến hành Cào dữ liệu & Tải song song]:::process
    SetupAnh --> KhoiDong
    SetupYT --> KhoiDong

    %% Chi tiết quá trình xử lý ngầm
    subgraph ThucThi ["Quá trình thực thi ngầm"]
        KhoiDong --> PhanLoai{Phân loại tài nguyên từ API}
        
        PhanLoai -- "Ảnh" --> KiemTraAnh{Chế độ nào?}
        KiemTraAnh -- "UC1, UC2" --> HangDoiTai
        KiemTraAnh -- "UC3" --> BoQuaAnh[Bỏ qua ảnh]:::storage
        
        PhanLoai -- "Video CDN" --> KiemTraCDN{Chế độ nào?}
        KiemTraCDN -- "UC1" --> HangDoiTai
        KiemTraCDN -- "UC2, UC3" --> BoQuaCDN[Bỏ qua CDN]:::storage

        PhanLoai -- "YouTube (DOM Icon)" --> KiemTraYT{Kiểm tra SQLite}
        KiemTraYT -- "Có DB Video Pending (UC1, UC3)" --> HangDoiYT[Đẩy vào Hàng đợi Click YT]:::process
        KiemTraYT -- "Không có Video Pending (UC2)" --> BoQuaYT[Quét DOM nhưng bỏ qua click]:::storage
        
        HangDoiYT --> LayLink[Truy vết Modal lấy link YT] --> HangDoiTai[Hàng đợi Tải xuống]
        
        HangDoiTai --> TaiFile[Tải tệp tin về .temp]:::process
        
        TaiFile --> KiemTraLocTrung{Chế độ nào?}
        KiemTraLocTrung -- "UC2 (Ảnh)" --> MD5Anh[So sánh MD5 ảnh]:::process
        KiemTraLocTrung -- "UC1, UC3 (Video)" --> FFmpegDedup[Lọc FFmpeg 3 bước: Length, Audio, dHash]:::process
        
        MD5Anh --> LuuTru[(Lưu vào thư mục đích)]:::storage
        FFmpegDedup --> LuuTru
    end
    
    LuuTru --> HoanTat([Hoàn tất & Dọn thư mục tạm])
```

---

## 2. Sơ đồ Tuần tự (Sequence Diagram)

Sơ đồ trình tự mô tả cách hệ thống áp dụng bộ lọc chế độ tải `download_mode` để phân phối tải và bật/tắt các luồng (Downloader/Dedup) một cách linh hoạt.

```mermaid
sequenceDiagram
    autonumber
    actor NguoiDung as Người dùng
    participant CLI as cli.py
    participant Core as core.py
    participant Scanner as sniffer.py
    participant DL as downloader.py
    participant Dedup as deduplication.py
    participant DB as SQLite (ad_metadata)

    NguoiDung->>CLI: Chọn Chế độ tải (UC1/UC2/UC3) & Khởi chạy
    CLI->>Core: Truyền tham số `download_mode` & Khởi động luồng
    activate Core
    
    %% Kích hoạt Deduplication (Thực tế code luôn bật nhưng chạy Idle nếu queue trống)
    Core->>Dedup: Luôn kích hoạt luồng FFmpeg Deduplication (Idle listening)
    Core->>DL: Khởi động Downloader threads
    Core->>Scanner: Khởi chạy Scraper thread
    deactivate Core

    activate Scanner
    loop Duyệt từng trang SocialPeta
        Scanner->>Scanner: Cuộn trang & Bắt gói tin API quảng cáo
        
        loop Mỗi quảng cáo trong API
            Scanner->>DB: Đã xử lý (pending/done) chưa?
            DB-->>Scanner: Chưa xử lý
            
            %% Lọc ngay từ Scanner
            alt Tải Ảnh nhưng Mode = UC3 (Chỉ YouTube)
                Scanner->>Scanner: BỎ QUA tài nguyên này
            else Tải Video CDN nhưng Mode = UC2 hoặc UC3
                Scanner->>Scanner: BỎ QUA tài nguyên này
            else Cần Click YouTube nhưng Mode = UC2 (Chỉ ảnh)
                Scanner->>Scanner: BỎ QUA tài nguyên này
            else Tài nguyên hợp lệ với Mode
                Scanner->>DB: Lưu trạng thái = pending
                Scanner->>DL: Đẩy URL vào hàng đợi tải (nếu là ảnh) HOẶC
                Scanner->>Scanner: Đẩy vào queue Click Youtube (nếu là YT)
            end
        end
        
        alt Nếu Mode = UC1 hoặc UC3
            Scanner->>Scanner: Gọi YoutubeService mở Modal, trích xuất link chuẩn, đẩy vào DL
        end
    end
    deactivate Scanner

    activate DL
    loop Mỗi tệp tin trong hàng đợi tải
        DL->>DL: Tải về .temp_download
        
        alt Tệp là Ảnh
            DL->>DL: Check MD5, nếu mới -> Di chuyển thư mục đích
        else Tệp là Video (Chỉ xảy ra ở UC1, UC3)
            DL->>Dedup: Đẩy video tạm vào hàng đợi lọc trùng
            activate Dedup
            Dedup->>Dedup: Quét FFmpeg: Length -> Audio PCM -> dHash
            Dedup->>DB: Nếu trùng -> Ghi log. Nếu mới -> Đổi tên & Lưu
            deactivate Dedup
        end
    end
    deactivate DL
```
