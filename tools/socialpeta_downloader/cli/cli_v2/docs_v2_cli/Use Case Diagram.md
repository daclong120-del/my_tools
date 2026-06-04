# Tài liệu Đặc tả Sơ đồ Use Case (Use Case Diagram)

Tài liệu này đặc tả các chức năng cốt lõi (Use Cases) của hệ thống **SocialPeta Downloader v2** mà Người dùng (Actor) có thể thực hiện thông qua giao diện CLI.

Để xem sơ đồ dưới dạng hình vẽ trực quan, bạn hãy mở chế độ **Markdown Preview** trong trình soạn thảo (nhấn tổ hợp phím `Ctrl + Shift + V` hoặc click vào biểu tượng Preview ở góc trên cùng bên phải).

---

## 1. Sơ đồ Use Case Đồ họa (Mermaid Diagram)

```mermaid
graph TD
    %% Định nghĩa các Actor (Tác nhân ngoại vi)
    classDef actor fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff,shape:doublecircle;
    classDef usecase fill:#0f172a,stroke:#a855f7,stroke-width:2px,color:#fff;
    classDef system fill:#2e1065,stroke:#f59e0b,stroke-width:2px,color:#fff;

    NguoiDung((Người dùng)):::actor
    ChromeDebug((Trình duyệt Chrome Debug)):::actor
    YoutubePlatform((Nền tảng YouTube)):::actor

    subgraph RanhGioiHeThong ["RANH GIỚI HỆ THỐNG SOCIALPETA DOWNLOADER CLI"]
        UC01([UC-01: Kết nối Chrome CDP]):::usecase
        UC02([UC-02: Cấu hình Chế độ & Số trang]):::usecase
        UC03([UC-03: Cuộn trang & Bắt gói tin API]):::usecase
        UC04([UC-04: Phân trang & Kích hoạt mềm Soft Trigger]):::usecase
        UC05([UC-05: Click lấy link YouTube chuẩn]):::usecase
        UC06([UC-06: Tải xuống tài nguyên song song]):::usecase
        UC07([UC-07: Lọc trùng lặp 3 lớp]):::usecase
        UC08([UC-08: Hiển thị thống kê Rich Dashboard]):::usecase
    end

    %% Mối quan hệ giữa Actor và Use Cases
    NguoiDung --> UC02
    NguoiDung --> UC08

    UC01 --- ChromeDebug
    UC03 --- ChromeDebug
    UC04 --- ChromeDebug
    
    UC05 --- ChromeDebug
    UC05 --- YoutubePlatform
    
    %% Quan hệ Include / Extend giữa các Use Case
    UC03 -.->|include| UC01
    UC04 -.->|include| UC03
    UC05 -.->|extend| UC04
    UC06 -.->|include| UC07
```

---

## 2. Đặc tả Chi tiết các Use Case (Use Case Specifications)

### UC-01: Kết nối Chrome CDP (Chrome DevTools Protocol)
- **Tác nhân**: Trình duyệt Chrome Debug.
- **Mô tả**: Hệ thống tự động kiểm tra cổng debug Chrome (mặc định `9222`) và kết nối để lấy danh sách các tab đang hoạt động.
- **Điều kiện tiên quyết**: Chrome phải được mở thủ công bằng lệnh debug `--remote-debugging-port=9222`.
- **Luồng sự kiện chính**:
  1. Hệ thống gửi yêu cầu HTTP GET tới địa chỉ `http://127.0.0.1:9222/json/list`.
  2. Chrome trả về danh sách các tab đang mở.
  3. Hệ thống lọc ra các tab có URL thuộc SocialPeta và hiển thị cho người dùng.
- **Ngoại lệ**: Nếu cổng `9222` không hoạt động, hệ thống sẽ đưa ra thông báo cảnh báo lỗi kết nối và yêu cầu người dùng mở lại Chrome đúng cách.

### UC-02: Cấu hình Chế độ & Số trang
- **Tác nhân**: Người dùng.
- **Mô tả**: Người dùng nhập các thiết lập ban đầu trước khi bắt đầu tải.
- **Luồng sự kiện chính**:
  1. Người dùng chọn tab SocialPeta cần cào.
  2. Người dùng nhập thư mục lưu kết quả.
  3. Người dùng chọn một trong các chế độ: *Chỉ tải ảnh, Chỉ tải Youtube, Tải tất cả (Tải full)*.
  4. Người dùng nhập số lượng trang muốn cào (ví dụ: cào từ trang 1 đến trang 5).
- **Điều kiện sau cùng**: Hệ thống khởi tạo các luồng tải xuống ngầm và luồng lọc trùng lặp dựa trên cấu hình đã chọn.

### UC-03: Cuộn trang & Bắt gói tin API
- **Tác nhân**: Trình duyệt Chrome Debug.
- **Mô tả**: Trình cào quét tự động bắt các gói tin API phản hồi từ SocialPeta chứa thông tin quảng cáo.
- **Luồng sự kiện chính**:
  1. Playwright điều khiển cuộn trang trình duyệt xuống dưới cùng.
  2. Hệ thống đón bắt (sniff) sự kiện `"response"` chứa endpoint `/creative/list` hoặc `/creative-rank/list`.
  3. Phân tích nội dung JSON trả về để bóc tách thông tin (`ad_id`, loại ảnh, video gốc CDN).
  4. Lưu trạng thái các tài nguyên thu thập được vào cơ sở dữ liệu SQLite dưới dạng trạng thái chờ (`pending`).

### UC-04: Phân trang & Kích hoạt mềm (Soft Trigger)
- **Tác nhân**: Trình duyệt Chrome Debug.
- **Mô tả**: Trình cào điều khiển click phím phân trang và kích hoạt nạp lại dữ liệu nếu bị đứng/mất gói tin.
- **Luồng sự kiện chính**:
  1. Playwright tìm nút trang tiếp theo trên giao diện web và click.
  2. Hệ thống đợi gói tin API của trang đó phản hồi.
  3. **Luồng thay thế (Soft Trigger)**: Nếu quá 30 giây không nhận được gói tin, hệ thống tự động thực hiện cuộn trang lên xuống hoặc click vào nút "Tìm kiếm" (Search) để bắt trang web gửi lại gói tin API mới.

### UC-05: Click lấy link YouTube chuẩn
- **Tác nhân**: Trình duyệt Chrome Debug, Nền tảng YouTube.
- **Mô tả**: Click nút "Chi tiết" trên thẻ quảng cáo để mở modal và cào link YouTube gốc.
- **Luồng sự kiện chính**:
  1. Hệ thống tìm kiếm các card quảng cáo có icon/chữ YouTube trên giao diện.
  2. Playwright điều khiển cuộn màn hình đến card đó và click nút **"Chi tiết"** (Detail).
  3. Đợi modal thông tin quảng cáo hiện ra.
  4. Trích xuất thuộc tính `src` của `iframe` YouTube hoặc thuộc tính `href` của đường dẫn YouTube.
  5. Đóng modal quảng cáo (nhấn phím ESC).
  6. Lưu đường dẫn video YouTube thực tế vào SQLite và xếp vào hàng đợi tải xuống.

### UC-06: Tải xuống tài nguyên song song
- **Tác nhân**: Không có (Hệ thống tự động).
- **Mô tả**: Các luồng xử lý tải xuống (Downloader Workers) lấy tài nguyên từ hàng đợi và tải về máy.
- **Luồng sự kiện chính**:
  1. Luồng tải lấy đường dẫn từ hàng đợi.
  2. Đối với ảnh: Tải trực tiếp về thư mục tạm.
  3. Đối với video YouTube: Gọi thư viện `yt-dlp` để tải luồng chất lượng cao nhất về thư mục tạm.
  4. Đối với video CDN gốc: Tải tệp tạm thông qua HTTP client thông thường.

### UC-07: Lọc trùng lặp 3 lớp
- **Tác nhân**: Không có (Hệ thống tự động).
- **Mô tả**: Lọc trùng video trước khi lưu chính thức vào thư mục đích của người dùng.
- **Luồng sự kiện chính**:
  1. **Bước 1 (Thời lượng)**: Kiểm tra chênh lệch thời lượng video bằng `ffprobe`. Nếu chênh lệch quá $0.05$ giây thì xem như không trùng.
  2. **Bước 2 (Âm thanh)**: Trích xuất âm thanh PCM bằng `ffmpeg` và so sánh mã hash MD5 của luồng âm thanh đó.
  3. **Bước 3 (Hình ảnh)**: Trích xuất 5 khung hình tại các thời điểm 10%, 30%, 50%, 70%, 90% thời lượng. So sánh khoảng cách Hamming (dHash) giữa các khung hình (khoảng cách $\le 13$ và chênh lệch độ sáng $\le 10\%$).
  4. **Quyết định**: Nếu trùng, xóa tệp tạm và ghi nhật ký vào `duplicate_audit.csv`. Nếu là duy nhất, lưu tệp vào thư mục đích.

### UC-08: Hiển thị thống kê Rich Dashboard
- **Tác nhân**: Người dùng.
- **Mô tả**: Hiển thị bảng thống kê trực tiếp trên giao diện console/terminal để người dùng theo dõi tiến độ cào tải.
- **Luồng sự kiện chính**:
  1. Màn hình tự động cập nhật liên tục các thông số:
     - Số tab đang hoạt động.
     - Trang hiện tại đang cào.
     - Số lượng ảnh/video đã phát hiện.
     - Đang chờ tải, đang tải, đã hoàn thành.
     - Số video bị trùng lặp đã lọc.


# Sơ đồ hoạt động chi tiết khi nhấn "Tải tất cả" (Tải full)

Để xem sơ đồ dưới dạng hình vẽ trực quan, bạn hãy mở chế độ **Markdown Preview** trong trình soạn thảo (trên VS Code, nhấn tổ hợp phím `Ctrl + Shift + V` hoặc click vào biểu tượng Preview ở góc trên cùng bên phải).

---

## 1. Sơ đồ Luồng Công Việc khi chọn "Tải tất cả" (Dạng lưu đồ)

Sơ đồ này mô tả chi tiết các bước từ lúc bạn bấm phím trên màn hình CLI, chọn chế độ "Tải tất cả" cho đến khi hệ thống tự động phân loại, tải xuống và lọc trùng lặp.

```mermaid
flowchart TD
    %% Định nghĩa Màu sắc hiển thị
    classDef menu fill:#2b3a4a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef process fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#fff;
    classDef storage fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef queue fill:#2e1065,stroke:#f59e0b,stroke-width:2px,color:#fff;

    BatDau([1. Khởi chạy CLI]) --> MenuChinh[2. Menu: Chọn trang cần tải]:::menu
    MenuChinh --> ChonTab[3. Chọn Tab Chrome đang mở]:::menu
    ChonTab --> ChonCheDo{4. Chọn Chế độ Tải}:::menu

    ChonCheDo -- "Chỉ tải ảnh" --> ModeAnh[Chỉ quét ảnh & ảnh thu nhỏ]:::process
    ChonCheDo -- "Chỉ tải YouTube" --> ModeYT[Chỉ quét và trích xuất Youtube]:::process
    
    ChonCheDo -- "Tải tất cả (Tải full)" --> ChonThuMuc["5. Chọn thư mục lưu & Số trang muốn tải"]:::menu
    
    ChonThuMuc --> KhoiDongHeThong["6. Khởi động các luồng xử lý ngầm"]:::process

    %% Khối thực thi song song viết hoàn toàn bằng tiếng Việt
    subgraph ThucThiSongSong ["TIẾN TRÌNH CHẠY SONG SONG"]
        direction TB
        
        %% Luồng Cào dữ liệu
        subgraph LuongCao ["A. Luồng cào dữ liệu (Chạy ngầm)"]
            direction LR
            TheoDoiAPI[Theo dõi gói tin API] --> PhanLoai{Phân loại tài nguyên}
            
            PhanLoai -- "Ảnh tĩnh / Tệp ảnh thu nhỏ" --> HangDoiTai["Hàng đợi tải xuống"]:::queue
            PhanLoai -- "Video Youtube (Có icon/chữ Youtube)" --> HangDoiYT["Hàng đợi xử lý click Youtube"]:::queue
            PhanLoai -- "Video gốc (CDN)" --> LuuTamJSON["Lưu tạm vào file JSON (Trì hoãn tải)"]:::storage
            
            HangDoiYT --> GiaLapClick[Playwright cuộn đến card & Click nút Chi tiết]:::process
            GiaLapClick --> LayLinkYT[Trích xuất đường dẫn Youtube thực]:::process
            LayLinkYT --> HangDoiTai
            
            LuuTamJSON -->|Đợi xử lý click xong mọi video Youtube| HangDoiTai
        end

        %% Luồng Tải xuống và Lọc trùng
        subgraph LuongTaiXuong ["B. Luồng tải xuống & Lọc trùng"]
            direction LR
            HangDoiTai --> TaiFileTam[Tải tệp tin về thư mục tạm]:::process
            
            TaiFileTam -- "Là Ảnh" --> KiemTraMD5{So sánh mã MD5 ảnh đã tải}:::process
            KiemTraMD5 -- "Ảnh mới" --> LuuThuMucAnh[(Thư mục lưu trữ đích)]:::storage
            KiemTraMD5 -- "Ảnh trùng" --> XoaAnhTam[Xóa tệp tạm]:::process
            
            TaiFileTam -- "Là Video" --> HangDoiLocTrung["Hàng đợi lọc trùng"]:::queue
            HangDoiLocTrung --> BoLoc3Lop{Lọc trùng 3 bước: Thời lượng -> Âm thanh -> Hình ảnh}:::process
            BoLoc3Lop -- "Video mới" --> LuuThuMucVideo[(Thư mục lưu trữ đích)]:::storage
            BoLoc3Lop -- "Video trùng" --> XoaVideoTam[Xóa tệp tạm & ghi nhật ký trùng]:::process
        end

        %% Bảng trạng thái CLI
        subgraph BangTheoDoi ["C. Bảng thống kê hiển thị màn hình"]
            CapNhat[Cập nhật liên tục: Đang chờ, Đang tải, Thành công, Trùng lặp...]:::menu
        end
    end

    KhoiDongHeThong --> ThucThiSongSong
    LuuThuMucAnh --> HoanTat([7. Hoàn tất & Dọn sạch thư mục tạm])
    LuuThuMucVideo --> HoanTat
```

---

## 2. Sơ đồ trình tự tương tác theo thời gian

Sơ đồ trình tự dưới đây thể hiện cách các thành phần trong code tương tác với nhau theo thứ tự trước sau khi bạn chọn **Tải tất cả**:

```mermaid
sequenceDiagram
    autonumber
    actor NguoiDung as Người dùng (Giao diện CLI)
    participant Core as Bộ điều khiển trung tâm
    participant Scanner as Trình quét Tab Chrome
    participant YT as Bộ xử lý YouTube
    participant DL as Luồng tải xuống
    participant Dedup as Bộ lọc trùng lặp
    participant DB as Cơ sở dữ liệu (SQLite)

    NguoiDung->>Core: Chọn "Tải tất cả" & Nhập số trang cần tải
    activate Core
    Core->>DL: Khởi tạo các luồng tải xuống song song
    Core->>Dedup: Khởi tạo luồng lọc trùng lặp video
    Core->>Scanner: Bắt đầu cào dữ liệu trang
    activate Scanner
    
    Note over Scanner: Playwright kết nối với trình duyệt Chrome qua cổng debug

    loop Trên từng trang (Trang 1 -> Trang cuối)
        Scanner->>Scanner: Cuộn trang để trang web tải thêm quảng cáo
        Note right of Scanner: Hệ thống bắt gói tin phản hồi chứa danh sách quảng cáo
        Scanner->>DB: Truy vấn kiểm tra xem ad_id này đã từng tải chưa?
        DB-->>Scanner: Chưa từng tải (Quảng cáo mới)
        Scanner->>DB: Đánh dấu trạng thái đang xử lý ("pending")

        alt Nếu quảng cáo là Tệp ảnh tĩnh (Ảnh thu nhỏ đại diện)
            Scanner->>DL: Đẩy trực tiếp đường dẫn vào hàng đợi tải xuống
        else Nếu quảng cáo là Video Youtube (Phát hiện icon/chữ Youtube trên DOM)
            Scanner->>Scanner: Đẩy thông tin vào hàng đợi xử lý click Youtube
        else Nếu quảng cáo là Video CDN (video gốc của Facebook/TikTok)
            Scanner->>Scanner: Lưu thông tin vào file JSON tạm thời (trì hoãn chưa tải)
        end

        Note over Scanner,YT: BẮT BUỘC xử lý click Youtube trước tiên
        loop Với mỗi quảng cáo Youtube trong hàng đợi xử lý click
            Scanner->>YT: Yêu cầu lấy link thực tế
            activate YT
            YT->>YT: Playwright cuộn tới card quảng cáo và nhấn nút "Chi tiết"
            YT->>YT: Đợi hộp thoại mở ra, trích xuất đường dẫn Youtube chuẩn
            YT->>DL: Đẩy đường dẫn Youtube chuẩn vào hàng đợi tải xuống
            YT->>DB: Cập nhật trạng thái = Thành công (Đã lấy được link)
            deactivate YT
        end

        Note over Scanner,DL: Sau khi xử lý xong hết video Youtube -> Mới đưa video CDN tạm vào hàng đợi
        Scanner->>DL: Đẩy toàn bộ video CDN từ file JSON tạm vào hàng đợi tải xuống
    end
    deactivate Scanner

    Note over DL,Dedup: Các luồng tải hoạt động song song để lưu trữ tệp tin
    activate DL
    loop Với mỗi tệp tin trong hàng đợi tải xuống
        DL->>DL: Tải tệp tin về thư mục tạm thời (.temp_download)
        
        alt Nếu tệp tin là Ảnh
            DL->>DL: So sánh mã MD5 của ảnh với các ảnh đã tải trước đó
            DL->>DB: Nếu không trùng -> Di chuyển vào thư mục đích & đặt trạng thái Done
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

    Core-->>NguoiDung: Hoàn tất, dọn dẹp các thư mục tạm thời & Quay lại Menu chính
    deactivate Core
```

---

## 3. Cơ chế chống click trùng lặp video YouTube

Để đảm bảo trình duyệt tự động (Playwright) không click lặp lại 2 lần vào cùng một video YouTube, hệ thống kết hợp 2 tầng bảo vệ đồng bộ với cơ sở dữ liệu SQLite:

### Tầng 1: Sử dụng bộ nhớ SQLite (`ad_metadata`) kiểm tra lịch sử tải
- Mỗi quảng cáo được xác định qua một mã định danh duy nhất là `ad_id` từ gói tin API.
- Trước khi đưa bất kỳ video nào vào hàng đợi xử lý click YouTube (`tab_youtube_queues`), hệ thống gọi hàm `_is_ad_already_downloading_or_done(ad_id)`.
- Nếu quảng cáo này đã tồn tại trong lịch sử SQLite với trạng thái đang tải hoặc hoàn thành (`pending`, `downloading`, `done`), hệ thống sẽ **bỏ qua ngay lập tức** mà không xử lý nữa.

### Tầng 2: Thay đổi Loại tài nguyên (Media Type) và Trạng thái sau khi click
Khi Playwright cào xong hoặc xử lý lỗi một card YouTube, loại và trạng thái của nó sẽ được cập nhật vĩnh viễn trong SQLite:
- **Nếu cào thành công**: Loại của quảng cáo đổi từ `video` hoặc `youtube_click_required` sang `youtube_video` (Đã có link YouTube chuẩn).
- **Nếu cào thất bại**: Trạng thái được cập nhật thành `failed`.
- **Nguyên lý loại trừ**: Hàm quét giao diện để phát hiện icon YouTube (`_upgrade_youtube_items_via_dom`) chỉ truy vấn từ DB các tài nguyên có loại là `video` gốc và đang chờ xử lý (`pending`). Do loại tài nguyên và trạng thái đã bị đổi sau khi click, nên trong các lượt cuộn trang tiếp theo hoặc ở các trang khác, quảng cáo này sẽ **bị bỏ qua hoàn toàn** và không bao giờ bị click lại.

---

## 4. Các cơ chế bổ trợ quan trọng khác

Để đảm bảo toàn bộ hệ thống hoạt động ổn định và tin cậy, code còn triển khai các cơ chế phụ trợ sau:

### 4.1. Trích xuất tên Ứng dụng/Nhà quảng cáo linh hoạt (DOM Fallback)
- **Hành vi**: Hệ thống trước tiên cố gắng lấy tên ứng dụng sạch từ tiêu đề của Tab trình duyệt Chrome.
- **Dự phòng (Fallback)**: Nếu tiêu đề không chứa tên ứng dụng hợp lệ (hoặc trả về `UnknownApp`), hệ thống sẽ tự động quét DOM của trang bằng Playwright qua hàm `_scrape_app_name_from_dom` để tìm các phần tử như `.advertiser-name`, `.app-title`, v.v.
- **Kết quả**: Tạo thư mục đích lưu trữ theo định dạng chuẩn: `{Tên_mạng_quảng_cáo}_{Tên_ứng_dụng}_{Ngày_tải}`.

### 4.2. Cơ chế phân trang tự động và Trình kích hoạt mềm (Soft Trigger)
- **Chuyển trang**: Hệ thống tự động click nút chuyển trang trên giao diện SocialPeta từ trang `1` đến trang `N`.
- **Kích hoạt mềm (Soft Trigger)**: Nếu sau khi click chuyển trang mà gói tin API không phản hồi (bị timeout), hàm `soft_trigger` sẽ được kích hoạt để cuộn trang lên xuống liên tục hoặc tự động click vào nút "Tìm kiếm" (Search) trên giao diện để kích thích trang web gửi lại gói tin API mới mà không gây treo luồng.

### 4.3. Dọn dẹp tệp tin tạm thời khi hoàn tất
- Trong suốt quá trình cào, các tệp tin được lưu trong thư mục tạm `.temp_download`.
- Khi tất cả hàng đợi đã xử lý xong và được lọc trùng thành công vào thư mục đích, toàn bộ các tệp tin tạm này sẽ được dọn dẹp sạch sẽ để tránh làm đầy dung lượng ổ đĩa của bạn.


