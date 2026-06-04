# Sơ đồ Tuần tự (Sequence Diagram)

Tài liệu này mô tả chi tiết trình tự tương tác theo dòng thời gian giữa các thành phần trong hệ thống **SocialPeta Downloader v2** khi thực hiện chế độ "Tải tất cả" (Tải full).

Để xem sơ đồ dưới dạng hình vẽ trực quan, bạn hãy mở chế độ **Markdown Preview** trong trình soạn thảo (nhấn tổ hợp phím `Ctrl + Shift + V` hoặc click vào biểu tượng Preview ở góc trên cùng bên phải).

---

## 1. Sơ đồ Tuần tự Chi tiết (Sequence Diagram)

Sơ đồ dưới đây thể hiện sự tương tác giữa: **Người dùng**, **giao diện CLI**, **Bộ điều khiển trung tâm (Core)**, **Trình cào (Scanner/Playwright)**, **Bộ click Youtube (YT)**, **Luồng tải (Downloader)**, **Bộ lọc trùng (Deduplicator)** và **Cơ sở dữ liệu (SQLite DB)**.

```mermaid
sequenceDiagram
    autonumber
    actor NguoiDung as Người dùng
    participant CLI as cli.py (Giao diện CLI)
    participant Core as core.py (Điều khiển)
    participant Scanner as sniffer.py (Trình cào)
    participant YT as youtube.py (Click Youtube)
    participant DL as downloader.py (Tải xuống)
    participant Dedup as deduplication.py (Lọc trùng)
    participant DB as SQLite DB (ad_metadata)

    %% Giai đoạn 1: Khởi động và kết nối
    NguoiDung->>CLI: Khởi chạy ứng dụng (run.bat)
    activate CLI
    CLI->>Core: Yêu cầu kết nối Chrome debug (cổng 9222)
    activate Core
    Core->>Core: Kết nối CDP (Chrome DevTools Protocol)
    Core-->>CLI: Trả về danh sách Tab đang mở
    deactivate Core
    CLI-->>NguoiDung: Hiển thị danh sách Tab & Menu chọn chế độ
    
    NguoiDung->>CLI: Chọn "Tải tất cả" & Nhập số trang cần tải
    CLI->>Core: Khởi chạy luồng cào & luồng tải song song
    activate Core
    Core->>DB: Khởi tạo bảng dữ liệu ad_metadata
    Core->>DL: Khởi động các luồng tải song song (Downloader threads)
    Core->>Scanner: Khởi chạy luồng cào quét (Scraper thread)
    deactivate Core

    %% Giai đoạn 2: Cào quét trang & Phân loại tài nguyên
    activate Scanner
    loop Với mỗi trang (từ 1 đến N)
        Scanner->>Scanner: Cuộn trang để trang web tải thêm quảng cáo
        Scanner->>Scanner: Bắt gói tin API phản hồi chứa danh sách quảng cáo
        
        loop Với mỗi quảng cáo (ad_id) trong gói tin API
            Scanner->>DB: Gọi hàm _is_ad_already_downloading_or_done(ad_id)
            activate DB
            DB-->>Scanner: Trả về trạng thái (đã tải / chưa tải)
            deactivate DB
            
            alt Nếu quảng cáo đã được xử lý (trạng thái pending/done)
                Scanner->>Scanner: Bỏ qua không tải lại
            else Nếu quảng cáo là Ảnh hoặc Ảnh thu nhỏ Youtube
                Scanner->>DL: Đẩy trực tiếp đường dẫn vào hàng đợi tải xuống
            else Nếu quảng cáo là Video Youtube (Phát hiện icon/chữ Youtube trên DOM)
                Scanner->>Scanner: Đẩy thông tin vào hàng đợi xử lý click Youtube
            else Nếu quảng cáo là Video CDN (video gốc của Facebook/TikTok)
                Scanner->>DB: Lưu trạng thái vào SQLite với status = pending, media_type = video (trì hoãn chưa tải)
            end
        end

        %% Xử lý lấy link Youtube trước
        Note over Scanner,YT: BẮT BUỘC xử lý click Youtube trước tiên
        loop Với mỗi quảng cáo Youtube trong hàng đợi xử lý click
            Scanner->>YT: Yêu cầu lấy link thực tế
            activate YT
            YT->>YT: Playwright cuộn tới card quảng cáo và nhấn nút "Chi tiết"
            YT->>YT: Đợi hộp thoại mở ra, trích xuất đường dẫn Youtube chuẩn
            YT->>DL: Đẩy đường dẫn Youtube chuẩn vào hàng đợi tải xuống
            YT->>DB: Cập nhật loại tài nguyên = youtube_video & trạng thái = pending
            deactivate YT
        end

        %% Xử lý video CDN sau
        Note over Scanner,DL: Sau khi xử lý xong hết video Youtube -> Mới đưa video CDN từ SQLite vào hàng đợi
        Scanner->>DB: Truy vấn danh sách video CDN có status = pending
        DB-->>Scanner: Trả về danh sách video CDN
        Scanner->>DL: Đẩy danh sách video CDN vào hàng đợi tải xuống
    end
    deactivate Scanner

    %% Giai đoạn 3: Luồng tải xuống & Lọc trùng lặp hoạt động song song
    activate DL
    loop Với mỗi tệp tin trong hàng đợi tải xuống
        DL->>DL: Tải tệp tin về thư mục tạm thời (.temp_download)
        
        alt Nếu tệp tin là Ảnh
            DL->>DL: So sánh mã MD5 của ảnh với các ảnh đã tải trước đó
            DL->>DB: Nếu không trùng -> Di chuyển vào thư mục đích & cập nhật SQLite
        else Nếu tệp tin là Video (CDN hoặc Youtube)
            DL->>Dedup: Đẩy video tạm vào hàng đợi lọc trùng
            activate Dedup
            Dedup->>Dedup: Bước 1: So sánh thời lượng video bằng ffprobe
            Dedup->>Dedup: Bước 2: So sánh mã MD5 của âm thanh PCM trích xuất bằng ffmpeg
            Dedup->>Dedup: Bước 3: So sánh hình ảnh dHash của 5 khung hình bằng ffmpeg
            
            alt Kết quả: Video bị trùng lặp
                Dedup->>Dedup: Xóa tệp tin tạm thời & Ghi nhật ký trùng lặp (duplicate_audit.csv)
            else Kết quả: Video mới (Độc nhất)
                Dedup->>Dedup: Đổi tên tệp tin theo chuẩn cấu trúc & Di chuyển về thư mục đích
                Dedup->>DB: Đặt trạng thái = Done (Thành công)
            end
            deactivate Dedup
        end
    end
    deactivate DL

    CLI-->>NguoiDung: Hoàn tất, dọn dẹp các thư mục tạm thời & Quay lại Menu chính
    deactivate CLI
```

---

## 2. Các điểm cốt lõi trong dòng tuần tự

### 2.1. Chống click trùng lặp YouTube
* Ở bước số **12** (`_is_ad_already_downloading_or_done`), hệ thống kiểm tra ngay trong cơ sở dữ liệu SQLite để xem ID quảng cáo đã từng được tải hoặc đang xử lý click chưa. Nếu rồi thì bỏ qua ngay.
* Ở bước số **23** (`Cập nhật loại tài nguyên = youtube_video`), sau khi lấy được liên kết YouTube thực tế, hệ thống cập nhật lại loại tài nguyên trong DB. Điều này giúp ngăn chặn trình duyệt click lại lần 2 vào quảng cáo này trong các lượt cuộn trang tiếp theo.

### 2.2. Nhận diện chính xác card YouTube (Tránh click nhầm Admob/các mạng khác)
* Ở bước số **21** (`Playwright cuộn tới card và nhấn nút "Chi tiết"`), thuật toán chấm điểm (Scoring Matcher) trong `youtube.py` lọc cứng và chỉ chấm điểm những card quảng cáo chứa icon của nền tảng YouTube (`.net-icon-youtube` hoặc tương đương). Nếu card không chứa icon YouTube, nó sẽ bị loại bỏ khỏi danh sách ứng viên click, ngăn chặn việc click nhầm vào các card quảng cáo của Admob, Facebook, TikTok... dù có trùng lặp hình ảnh/video hash hoặc App Name.

### 2.3. Trì hoãn tải Video CDN gốc
* Do video CDN của SocialPeta thường dễ tải hơn và không cần tương tác nhấp chuột, hệ thống trì hoãn việc tải chúng bằng cách lưu thông tin trực tiếp vào cơ sở dữ liệu SQLite dưới trạng thái chờ (`pending`).
* Hệ thống chỉ truy vấn các bản ghi video CDN này từ SQLite để đưa vào hàng đợi tải xuống sau khi đã hoàn thành click mở modal để cào hết tất cả các đường dẫn video YouTube trên trang hiện tại. Điều này tối ưu hóa việc phân phối tài nguyên hệ thống, tránh sử dụng các file JSON tạm thời làm mất đồng bộ dữ liệu và không làm nghẽn luồng xử lý của trình duyệt Playwright.
