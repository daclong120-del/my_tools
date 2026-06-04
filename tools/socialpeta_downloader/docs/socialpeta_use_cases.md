# Tài Liệu Use Case — socialpeta_downloader

> Phiên bản: 1.0 | Tổng hợp toàn bộ UC đã thống nhất

---

## Tổng quan dự án

**Mục tiêu:** Thu thập tự động dữ liệu quảng cáo (video, ảnh, metadata) từ SocialPeta thông qua điều khiển Chrome, không reload trang để giữ nguyên bộ lọc đang chọn.

**Các file chính:**

- `main.py` — Entrypoint, CLI chính
- `src/cli/socialpeta_cli.py` — Bento Menu UI, kết nối Chrome Debug
- `src/scrapers/socialpeta.py` — Scraper cốt lõi, network sniffing
- `src/core/deduplicator.py` — Bộ lọc trùng lặp 3 tầng
- `src/core/sys_monitor.py` — Giám sát CPU/RAM, tính số luồng tối ưu

**Nguyên tắc bất biến:**

- Không bao giờ F5 / reload trang (mất bộ lọc)
- Điều hướng trang bằng click DOM
- Bắt dữ liệu qua network sniffing (`page.listen`), không cào DOM thô

---

## Kiến trúc luồng

### Trường hợp 1 tab:

```
Scraper thread × 1      →  .temp/tabN/   (ghi link + trạng thái)
Download pool  × 1      →  N workers     (tải video/ảnh)
Filter thread  × 1      →  lọc trùng 3 tầng, ghi file chính thức
```

### Trường hợp K tab (đa tab):

```
Scraper thread × K      →  .temp/tab4/  .temp/tab5/  .temp/tab6/
Download pool  × 1      →  N workers, quét TẤT CẢ thư mục tạm cùng lúc
Filter thread  × 1      →  singleton, xử lý output từ tất cả tab
```

**Tài nguyên dùng chung giữa tất cả tab:**

- `download_semaphore` — giới hạn tổng worker tải đồng thời
- `naming_lock` — STT global tăng atomic khi đặt tên file
- `history_lock` — tránh tải cùng `ad_key` từ 2 tab
- `metadata_lock` — tránh ghi đè `download_info.csv`
- `item_lock` per item — tránh 2 worker nhận cùng 1 pending item

---

## Quy tắc đặt tên file

**Cấu trúc:** `TenApp_SPY_DDMMYYYY_STT.ext`

**Ví dụ:** `VoiceChanger_SPY_29052026_1.mp4`, `ReelSpell_SPY_10032026_3.jpg`

| Thành phần | Nguồn                     | Quy tắc                                                                       |
| ---------- | ------------------------- | ----------------------------------------------------------------------------- |
| `TenApp`   | `app_name` trong metadata | Bỏ ký tự đặc biệt + stopword (`by`, `for`, `app`...), lấy 2 từ đầu PascalCase |
| `SPY`      | Cố định                   | Không thay đổi                                                                |
| `DDMMYYYY` | Ngày tải                  | 8 chữ số, không dấu phân cách, padding 0 nếu cần                              |
| `STT`      | Global counter            | Tăng atomic toàn session, reset khi khởi động lại, không padding 0            |
| `.ext`     | Loại media                | `.mp4` cho video, `.jpg/.png/.webp` cho ảnh (giữ đúng extension gốc)          |

**Xử lý tên đặc biệt:**

- `app_name` trống / null → dùng `UnknownApp`
- Tên app toàn ký tự unicode (tiếng Trung, Nhật...) → giữ nguyên 2 từ đầu
- Sau xử lý còn ký tự không hợp lệ với filesystem → strip, chỉ giữ `[A-Za-z0-9]`

---

## Cấu trúc file dữ liệu & Workspace

### `db.sqlite3` (Database SQLite động)

Tệp database lưu trữ lịch sử tải xuống và siêu dữ liệu của ứng dụng.
- **Vị trí lưu trữ:** Luôn nằm động trực tiếp tại thư mục tải xuống hiện tại được chọn (`settings.DOWNLOAD_DIR`).
- **Đường dẫn tệp tin (`saved_path`):** Đường dẫn file tải về lưu trong DB phải là đường dẫn tương đối (Relative Path) tính từ `DOWNLOAD_DIR` (ví dụ: `App_Name/video.mp4` thay vì `C:\Users\<Tên_User>\Downloads\SocialPeta_Downloader\App_Name\video.mp4`). Điều này đảm bảo tính di động khi người dùng sao chép hoặc di chuyển toàn bộ thư mục.
- **Khi đổi thư mục tải xuống:** Hệ thống ngắt kết nối database cũ, mở/tạo tệp `db.sqlite3` mới tại thư mục mới và tự động khởi tạo lại cấu trúc bảng.

### `download_temp.json` (per tab, trong `.temp/tabN/`)

Lưu danh sách link cần tải và trạng thái xử lý.

**Trạng thái item:**

- `pending` — scraper đã ghi link, chưa ai tải
- `downloading` — một worker đang tải
- `done` — tải xong, đã đẩy sang filter
- `failed` — lỗi sau N lần retry
- `expired` — CDN URL hết hạn

### `download_info.csv` (output báo cáo)

File tổng hợp metadata tất cả media đã tải thành công, được tự động xuất/ghi đè từ SQLite ra thư mục tải xuống gốc (`DOWNLOAD_DIR`).

**Các field đầy đủ:**

| Field                          | Mô tả                                                         |
| ------------------------------ | ------------------------------------------------------------- |
| `video_name`                   | Tên file cuối cùng (theo quy tắc đặt tên)                     |
| `media_type`                   | `video` / `youtube_video` / `youtube_thumbnail` / `image`     |
| `ad_key`                       | ID quảng cáo duy nhất từ SocialPeta                           |
| `app_name`                     | Tên ứng dụng đầy đủ (gốc)                                     |
| `publisher`                    | Nhà phát hành                                                 |
| `platform`                     | Nền tảng quảng cáo                                            |
| `popularity`                   | Độ phổ biến                                                   |
| `number_of_days_of_deployment` | Số ngày chạy quảng cáo                                        |
| `deployment_time`              | Khoảng thời gian chạy (dạng `YYYY-MM-DD~YYYY-MM-DD`)          |
| `finally_saw`                  | Lần cuối xuất hiện                                            |
| `estimated_value`              | Giá trị ước tính                                              |
| `impression`                   | Số lần hiển thị                                               |
| `heat`                         | Chỉ số nhiệt                                                  |
| `copywriting_language`         | Ngôn ngữ nội dung                                             |
| `area`                         | Khu vực địa lý                                                |
| `title`                        | Tiêu đề quảng cáo                                             |
| `body`                         | Nội dung quảng cáo                                            |
| `video_url`                    | URL video CDN (để trống nếu là ảnh hoặc YouTube thumbnail)    |
| `youtube_url`                  | URL YouTube (để trống nếu không phải YouTube)                 |
| `duration`                     | Thời lượng video (giây), `0` nếu YouTube 0s, trống nếu là ảnh |
| `download_time`                | Timestamp tải về (`YYYY-MM-DD HH:MM:SS`)                      |

**Nguyên tắc:** Không để trống bất kỳ field metadata nào mà API đã trả về. Chỉ để trống các field kỹ thuật không áp dụng cho loại media đó. File CSV phải sử dụng mã hóa UTF-8 có BOM để hiển thị chính xác các ký tự đặc biệt khi mở bằng Microsoft Excel.

---

## Nhóm UC-01 — Khởi động chương trình

### UC-01: Khởi động chính

**Luồng chính:**

1. User mở SocialPeta trên Chrome với debug port đúng.
2. Chạy lệnh khởi động, nhập số luồng tải mong muốn.
3. `sys_monitor` kiểm tra CPU/RAM, xác nhận số luồng phù hợp.
4. Kết nối Chrome debug port, xác nhận kết nối thành công.
5. Hiển thị Bento Menu CLI.

**Ngoại lệ:**

- `UC-01a` Chrome chưa mở hoặc sai port → in cảnh báo rõ ràng, hướng dẫn mở lại đúng port
- `UC-01b` Không tìm thấy tab SocialPeta → chờ và retry mỗi 5 giây, không crash
- `UC-01c` Số luồng nhập vượt ngưỡng an toàn → cảnh báo, tự giảm xuống giá trị tối đa khuyến nghị

---

## Nhóm UC-T — Quản lý Tab Chrome

### UC-T01: Quét và hiển thị danh sách tab SocialPeta

**Trigger:** Khởi động chương trình hoặc user bấm `[R]`.

**Luồng chính:**

1. Gọi `context.pages` / `page.get_tabs()`, lọc URL chứa `socialpeta.com`.
2. Hiển thị danh sách dạng:

```
Phát hiện 3 tab SocialPeta:
  [4] Tab #4 — socialpeta.com/creative?app=VoiceChanger   trang 2
  [5] Tab #5 — socialpeta.com/creative?app=CapCut         trang 1
  [6] Tab #6 — socialpeta.com/creative-rank?...           trang 1

  [A] Tải tất cả    [R] Làm mới    [Q] Thoát
```

3. User chọn tab hoặc tải tất cả.

**Thông tin hiển thị mỗi tab:** Số tab thực trong Chrome, URL đầy đủ, loại trang (Ad Search / Creative Rank...), trang đang đứng.

**Ngoại lệ:**

- `UC-T01a` Không có tab SocialPeta nào → cảnh báo, gợi ý mở tab rồi bấm `[R]`
- `UC-T01b` Chrome chưa mở hoặc debug port không phản hồi → thông báo lỗi rõ, không crash
- `UC-T01c` Tab đang loading (URL `about:blank`) → hiển thị `(đang tải...)`, không đưa vào danh sách chọn

### UC-T02: Làm mới danh sách tab

**Trigger:** User mở thêm tab SocialPeta mới sau khi chương trình đã chạy, bấm `[R]`.

**Luồng chính:**

1. Gọi lại `context.pages`, so sánh với danh sách cũ.
2. Tab mới → badge `[NEW]`.
3. Tab đang chạy tải → badge `[ĐANG TẢI]`, không interrupt.
4. Tab cũ đã bị đóng → gỡ khỏi danh sách, dừng scraper thread tương ứng duyên dáng.

### UC-T03: Chọn tải một tab cụ thể

**Trigger:** User nhập số tab, ví dụ `4`.

**Luồng chính:**

1. Hỏi số trang muốn tải (mặc định 2).
2. Tạo thư mục `.temp/tab4/` nếu chưa có.
3. Spawn `Scraper #4` — daemon thread, gắn với Tab #4.
4. Download pool và Filter thread đã chạy sẵn, tự phát hiện `.temp/tab4/` có item mới.
5. CLI trả về menu ngay, không block.

**Ngoại lệ:**

- `UC-T03a` Tab đang có scraper chạy rồi → thông báo `"Tab #4 đang chạy rồi"`, không spawn thêm

### UC-T04: Tải tất cả tab cùng lúc

**Trigger:** User chọn `[A]`.

**Luồng chính:**

1. Hỏi cấu hình một lần: số trang, số worker tải tối đa.
2. Với mỗi tab chưa có scraper → tạo `.temp/tabN/`, spawn `Scraper #N`.
3. Download pool và Filter thread — nếu chưa chạy thì start, đang chạy thì không làm gì thêm.
4. Tất cả scraper song song, đẩy link vào thư mục tạm riêng. Download pool tự quét tất cả.

**Phân bổ worker:** `sys_monitor` tính tổng worker tối đa cho toàn máy. Pool tự cân bằng theo queue nào có item trước thì tải trước, không chia theo tab.

**Ngoại lệ:**

- `UC-T04a` Số tab × workers vượt ngưỡng phần cứng → `sys_monitor` giới hạn tổng, chia đều lại, cảnh báo user
- `UC-T04b` Một tab bị lỗi giữa chừng → chỉ dừng scraper tab đó, các tab còn lại tiếp tục
- `UC-T04c` Tranh chấp lock cao khi nhiều tab ghi CSV đồng thời → lock timeout hợp lý, không wait vô hạn

### UC-T05: Download pool theo dõi đa queue

**Cơ chế:**

1. Pool không gắn với tab cụ thể — quét tất cả `.temp/tabN/` tìm item `pending`.
2. Worker rảnh → lấy item `pending` theo FIFO toàn cục → đánh dấu `downloading` → tải → đánh dấu `done`.
3. Chuyển trạng thái sang `downloading` dùng atomic file rename hoặc `item_lock` tránh race condition.

**Ngoại lệ:**

- `UC-T05a` Hai worker cùng thấy một item `pending` → atomic lock khi nhận item, chỉ một worker thành công
- `UC-T05b` Scraper đang ghi item mới trong khi pool đang quét → không cần lock, pool chỉ đọc trạng thái

### UC-T06: Kích hoạt lại tab không phản hồi (Soft trigger)

**Vấn đề:** Tab mới mở, chương trình thấy tab nhưng không bắt được gói tin API.
**Tuyệt đối không F5.**

**Luồng chính:**

1. Scraper chờ gói tin, timeout sau 15 giây.
2. Soft trigger: mô phỏng click bộ lọc hoặc cuộn trang → ép SocialPeta gửi lại API request.
3. Retry tối đa 3 lần.
4. Vẫn không có → cảnh báo: `"Tab #N không phản hồi — hãy thao tác thủ công"`.

User cũng có thể chủ động bấm `[L] Kích hoạt lại tab` trong CLI menu bất kỳ lúc nào.

### UC-T07: Theo dõi trạng thái realtime đa tab

```
[4] VoiceChanger  trang 2/3  | thu: 47  tải: 31  lỗi: 2  trùng: 3
[5] CapCut        trang 1/2  | thu: 20  tải: 20  lỗi: 0  trùng: 1
[6] ReelSpell     xong       | thu: 60  tải: 58  lỗi: 0  trùng: 2

Worker pool: 4/6 đang bận  |  Queue tổng: 18 pending
```

---

## Nhóm UC-P — Pagination (Điều hướng trang)

### UC-P01: Nhập số trang trước khi chạy

**Trigger:** User chọn tab trong CLI menu.

**Luồng chính:**

1. CLI hỏi: `Số trang muốn tải? (mặc định: 2):`
2. Nhấn Enter không nhập → dùng mặc định `2`.
3. Nhập số nguyên dương → dùng giá trị đó.

**Ngoại lệ:**

- `UC-P01a` Nhập không hợp lệ (chữ, số âm, 0) → hỏi lại, không crash
- `UC-P01b` Nhập lớn hơn tổng trang thực tế → phát hiện khi đến trang cuối, dừng sớm

### UC-P02: Thuật toán điều hướng trang (không reload)

**Quy tắc điều hướng — Trang 1 luôn được click CUỐI CÙNG:**

| Số trang yêu cầu | Thứ tự click DOM                            | Lý do                                                                |
| ---------------- | ------------------------------------------- | -------------------------------------------------------------------- |
| 1 trang          | Click trang 2 → click lại trang 1           | Trang 1 đang hiển thị sẵn, cần rời đi rồi quay lại để có API request |
| 2 trang          | Click trang 2 → click trang 1               | Thu trang 2 trước, trang 1 sau                                       |
| N trang          | Click trang 2 → 3 → ... → N → click trang 1 | Trang 1 luôn là lần click cuối                                       |

### UC-P03: Bắt gói tin mỗi trang

**Luồng chính:**

1. Sau mỗi click DOM → `page.listen` chờ gói tin từ `/creative/list` hoặc `/creative-rank/list`.
2. Bắt được → parse JSON → đẩy toàn bộ creative list vào `.temp/tabN/`.
3. Chuyển sang click trang tiếp theo trong chuỗi điều hướng.

**Ngoại lệ:**

- `UC-P03a` Timeout không bắt được gói tin → fallback soft trigger (click bộ lọc / cuộn trang), retry 3 lần, bỏ qua trang nếu vẫn thất bại
- `UC-P03b` `creative_list` rỗng → đã vượt quá tổng trang thực, dừng vòng lặp sớm
- `UC-P03c` Nút trang bị disabled → đang ở trang cuối, phát hiện state disabled trước khi click, dừng sớm

### UC-P04: Xử lý Jump to Page

**Khi nào dùng:** Trang đích > 5 (các nút số trang chỉ hiện đến 5, sau đó là `...`).
Thay vì click `>` nhiều lần, gõ số vào ô "Jump to" và Enter để nhảy thẳng.

**Ngoại lệ:**

- `UC-P04a` Ô Jump to không nhận input → fallback về click mũi tên `>` nhiều lần
- `UC-P04b` Nhảy đến trang không tồn tại → SocialPeta redirect về trang cuối, phát hiện qua số trang trong JSON response

### UC-P05: Phối hợp pagination và luồng tải

- Scraper click trang → đẩy queue → click trang tiếp theo ngay, **không chờ** Download pool tải xong.
- Download pool tự tiêu thụ queue theo tốc độ riêng.

**Ngoại lệ:**

- `UC-P05a` Queue tích lũy nhiều khi pool chưa kịp xử lý → bình thường, queue unbounded không block Scraper
- `UC-P05b` Scraper xong tất cả trang, pool vẫn đang tải → Scraper kết thúc, pool tiếp tục cho đến khi queue rỗng
- `UC-P05c` Cùng `ad_key` xuất hiện ở nhiều trang → `download_history` check `ad_key` trước khi tải, bỏ qua duplicate sớm

---

## Nhóm UC-M — Phân loại và tải Media

### UC-M01: Phân loại media trước khi tải

| Điều kiện từ metadata                                 | Loại                  | Hành động                    |
| ----------------------------------------------------- | --------------------- | ---------------------------- |
| `video_url` có giá trị, không phải YouTube            | Video CDN             | Tải trực tiếp qua `requests` |
| `youtube_url` có giá trị VÀ `duration > 0`            | Video YouTube         | Resolve + tải qua `yt-dlp`   |
| `youtube_url` có giá trị VÀ `duration == 0` hoặc null | YouTube 0s (video ma) | Tải ảnh thumbnail thay thế   |
| `video_url` trống, chỉ có `image_url`                 | Ảnh tĩnh              | Tải ảnh trực tiếp            |

### UC-M02: Tải video CDN thường

- Tải qua `requests`, lưu vào `.temp/tabN/`, đẩy vào filter queue.
- Đặt tên: `TenApp_SPY_DDMMYYYY_STT.mp4`

**Ngoại lệ:**

- `UC-M02a` Mất kết nối giữa chừng → retry với exponential backoff, sau N lần → đánh dấu `failed`
- `UC-M02b` File tải về corrupt (0 byte) → xóa file tạm, đánh dấu lại `pending`
- `UC-M02c` Đĩa cứng đầy → dừng tải, thông báo ngay, không để file nửa chừng
- `UC-M02d` CDN URL hết hạn (403) → đánh dấu `expired`, không retry vô hạn

### UC-M03: Tải video YouTube (duration > 0)

1. Dùng `yt-dlp` với `youtube_url` để resolve URL stream thực.
2. Tải video, lưu vào `.temp/tabN/`.
3. Đẩy vào filter queue để qua bộ lọc 3 tầng bình thường.

**Ngoại lệ:**

- `UC-M03a` `yt-dlp` không resolve được (bị xóa / private / region lock) → ghi log `youtube_unavailable`, đánh dấu `failed`, không fallback tải ảnh
- `UC-M03b` `yt-dlp` trả về nhiều format → ưu tiên chất lượng cao nhất có audio

### UC-M04: Xử lý YouTube 0s (video ma)

Video có `youtube_url` nhưng `duration == 0` — không tải video, tải thumbnail thay thế.

**Luồng chính:**

1. Phát hiện `duration == 0`.
2. Không cố tải video.
3. Lấy `image_url` / thumbnail từ metadata.
4. Tải ảnh thumbnail, lưu thẳng vào thư mục đích (không qua filter queue video).
5. Ghi `download_info.csv` với `media_type = "youtube_thumbnail"`.

**Đặt tên:** `TenApp_SPY_DDMMYYYY_STT.jpg`

**Ngoại lệ:**

- `UC-M04a` Không tìm được thumbnail → ghi record với `video_name` trống, đánh dấu `no_media`
- `UC-M04b` Thumbnail URL hết hạn (403) → ghi log, đánh dấu `failed`

### UC-M05: Tải ảnh tĩnh (Image Ads)

1. Xác nhận `video_url` trống, có `image_url`.
2. Tải ảnh qua `requests`, lưu thẳng vào thư mục đích (bỏ qua `.temp` và filter queue video).
3. Ghi `download_info.csv` với `media_type = "image"`.

**Đặt tên:** Giữ đúng extension gốc (`.jpg` / `.png` / `.webp`).

**Ngoại lệ:**

- `UC-M05a` Ảnh tải về corrupt (0 byte) → xóa file, đánh dấu `failed`, không ghi CSV
- `UC-M05b` URL ảnh CDN hết hạn → ghi log, đánh dấu `failed`

### UC-M06: Bảng field download_info.csv theo loại media

| Field                   | Video CDN   | Video YouTube   | YouTube 0s          | Ảnh tĩnh    |
| ----------------------- | ----------- | --------------- | ------------------- | ----------- |
| `video_name`            | `.mp4`      | `.mp4`          | `.jpg/.png`         | `.jpg/.png` |
| `media_type`            | `video`     | `youtube_video` | `youtube_thumbnail` | `image`     |
| `video_url`             | URL CDN     | ``              | ``                  | ``          |
| `youtube_url`           | ``          | URL YouTube     | URL YouTube         | ``          |
| `duration`              | giây thực   | giây thực       | `0`                 | ``          |
| Các field metadata khác | điền đầy đủ | điền đầy đủ     | điền đầy đủ         | điền đầy đủ |

### UC-M07: Lấy URL YouTube ẩn (`find_youtube_url_for_image`)

Khi creative bắt nguồn YouTube, SocialPeta chỉ hiển thị ảnh tĩnh. Hệ thống tự động:

1. Cuộn đến card trên DOM.
2. Click mở Modal "App Info".
3. Quét DOM tìm thẻ `iframe`, trích xuất YouTube Video ID.
4. Trả về `youtube_url` đầy đủ.

**Ngoại lệ:**

- `UC-M07a` Modal không mở được (timeout) → retry N lần, ghi `youtube_url: ""` nếu thất bại
- `UC-M07b` iframe không chứa YouTube URL hợp lệ → ghi giá trị rỗng, log cảnh báo
- `UC-M07c` Card đã bị scroll off screen → cuộn lại trước khi click

### UC-M08: Lọc trùng lặp cho ảnh

Ảnh tĩnh và YouTube thumbnail không đi qua bộ lọc 3 tầng video. Dùng cơ chế đơn giản hơn:

1. Tính MD5 của file ảnh vừa tải.
2. So với cache MD5 ảnh đã lưu trong memory.
3. Trùng → xóa file mới, không ghi CSV.
4. Không trùng → lưu chính thức, ghi CSV, thêm MD5 vào cache.

---

## Nhóm UC-D — Lọc trùng lặp video 3 tầng (`deduplicator.py`)

### UC-D01: Tầng 1 — So sánh thời lượng

- Dùng `ffprobe` đọc thời lượng hai video.
- Chênh lệch > 0.05 giây → KHÔNG TRÙNG, kết thúc ngay.
- Chênh lệch ≤ 0.05 giây → chuyển sang Tầng 2.

### UC-D02: Tầng 2 — So sánh âm thanh PCM MD5

- Dùng `ffmpeg` trích xuất audio PCM (16kHz, mono).
- So sánh MD5 của chuỗi dữ liệu raw.
- MD5 khớp → TRÙNG LẶP, kết thúc.
- MD5 khác → chuyển sang Tầng 3.

**Ngoại lệ:**

- `UC-D02a` Video không có âm thanh (silent ad) → bỏ qua Tầng 2, chuyển thẳng Tầng 3

### UC-D03: Tầng 3 — So sánh hình ảnh dHash & Brightness

1. Trích xuất N khung hình dựa trên độ dài video.
2. Tính dHash (64-bit) và độ sáng trung bình từng khung hình.
3. So sánh: khoảng cách Hamming ≤ 5 VÀ delta độ sáng ≤ 15.0.
4. Tỷ lệ khung hình thỏa điều kiện ≥ 80% → TRÙNG LẶP.
5. Dưới 80% → KHÔNG TRÙNG.

### UC-D04: Xử lý kết quả lọc

- TRÙNG → xóa file tạm trong `.temp/`, không ghi CSV, không di chuyển.
- KHÔNG TRÙNG → di chuyển file từ `.temp/` sang thư mục đích, đổi tên theo quy tắc, ghi `download_info.csv`, thêm vân tay video vào cache.

**Ngoại lệ:**

- `UC-D04a` `ffprobe` / `ffmpeg` chưa cài hoặc sai version → kiểm tra khi khởi động, thông báo lỗi rõ trước khi bắt đầu
- `UC-D04b` File bị xóa trước khi filter xử lý (race condition) → kiểm tra file tồn tại trước khi so sánh, bỏ qua nếu không thấy
- `UC-D04c` Video gốc (đã lưu lâu) bị xóa thủ công → khi phát hiện bản gốc mất, thăng cấp bản mới thành gốc thay vì xóa
- `UC-D04d` `download_info.csv` đang bị ghi bởi thread khác → dùng `metadata_lock`, không ghi đè

---

## Nhóm UC-S — Quản lý phiên làm việc (Session)

### UC-S01: Tiếp tục sau khi tắt máy / crash

- Khi khởi động lại, đọc tất cả `.temp/tabN/`, tìm item `pending` hoặc `downloading`.
- Item `downloading` mà không có file tạm tương ứng (crash giữa chừng) → reset về `pending`.
- Tiếp tục tải, không cào lại từ đầu.

### UC-S02: Xem trạng thái tổng quan (CLI dashboard)

User xem được: tổng đã tải, đang tải, chờ, lỗi, trùng — không cần mở file JSON thủ công.

### UC-S03: Thay đổi số luồng lúc đang chạy

User muốn tăng / giảm số worker mà không restart chương trình.

- `sys_monitor` điều chỉnh `download_semaphore` động.
- Không interrupt worker đang tải dở.

---

## Nhóm UC-R — Tài nguyên hệ thống (`sys_monitor.py`)

### UC-R01: Tính số luồng tối ưu khi khởi động

- Đọc số nhân CPU và RAM khả dụng.
- Trả về số worker tối đa khuyến nghị cho máy hiện tại.
- Máy yếu (RAM < 4GB) → tự động giới hạn tối đa 2 workers, cảnh báo user.

### UC-R02: Giám sát tài nguyên khi đang chạy

- RAM vượt ngưỡng an toàn → tạm dừng spawn worker mới, chờ RAM giảm.
- CPU > 90% kéo dài → giảm số worker đang hoạt động, ưu tiên tài nguyên cho Scraper.

---

## Nhóm UC-O — Xuất báo cáo và tra cứu

### UC-O01: Thống kê sau phiên tải

Hiển thị: tổng video, tổng ảnh, tổng dung lượng, phân bố theo `platform`, `area`, `app_name`.

### UC-O02: Audit log video bị xóa do trùng lặp

Lưu danh sách video bị filter xóa (tên file, lý do, timestamp) để user kiểm tra lại nếu cần.

### UC-O03: Lọc download_info.csv theo tiêu chí

User lọc theo: `platform`, `area`, `app_name`, khoảng `deployment_time`, `media_type`...

---

## Bảng tổng hợp tất cả UC

| Mã UC  | Tên                               | Nhóm       |
| ------ | --------------------------------- | ---------- |
| UC-01  | Khởi động chương trình            | Khởi động  |
| UC-T01 | Quét danh sách tab SocialPeta     | Tab        |
| UC-T02 | Làm mới danh sách tab             | Tab        |
| UC-T03 | Chọn tải một tab                  | Tab        |
| UC-T04 | Tải tất cả tab cùng lúc           | Tab        |
| UC-T05 | Download pool theo dõi đa queue   | Tab        |
| UC-T06 | Kích hoạt lại tab không phản hồi  | Tab        |
| UC-T07 | Theo dõi trạng thái realtime      | Tab        |
| UC-P01 | Nhập số trang                     | Pagination |
| UC-P02 | Thuật toán điều hướng trang       | Pagination |
| UC-P03 | Bắt gói tin mỗi trang             | Pagination |
| UC-P04 | Jump to Page                      | Pagination |
| UC-P05 | Phối hợp pagination và luồng tải  | Pagination |
| UC-M01 | Phân loại media                   | Media      |
| UC-M02 | Tải video CDN                     | Media      |
| UC-M03 | Tải video YouTube                 | Media      |
| UC-M04 | Xử lý YouTube 0s                  | Media      |
| UC-M05 | Tải ảnh tĩnh                      | Media      |
| UC-M06 | Mapping field CSV theo loại media | Media      |
| UC-M07 | Lấy URL YouTube ẩn                | Media      |
| UC-M08 | Lọc trùng lặp ảnh                 | Media      |
| UC-D01 | Lọc tầng 1 — thời lượng           | Dedup      |
| UC-D02 | Lọc tầng 2 — âm thanh PCM         | Dedup      |
| UC-D03 | Lọc tầng 3 — dHash hình ảnh       | Dedup      |
| UC-D04 | Xử lý kết quả lọc                 | Dedup      |
| UC-S01 | Tiếp tục sau crash / tắt máy      | Session    |
| UC-S02 | CLI dashboard trạng thái          | Session    |
| UC-S03 | Thay đổi số luồng lúc đang chạy   | Session    |
| UC-R01 | Tính số luồng tối ưu              | Tài nguyên |
| UC-R02 | Giám sát tài nguyên realtime      | Tài nguyên |
| UC-O01 | Thống kê sau phiên tải            | Báo cáo    |
| UC-O02 | Audit log video bị xóa            | Báo cáo    |
| UC-O03 | Lọc CSV theo tiêu chí             | Báo cáo    |

UC bổ sung:
| UC-F01 | Chọn thư mục lưu file qua File Explorer | File/Workspace |
| UC-F02 | Đồng bộ Workspace và SQLite             | File/Workspace |

---

## UC-F01 — Chọn thư mục lưu file qua File Explorer

**Trigger:** Lần đầu khởi động, hoặc user bấm "Đổi thư mục lưu" trong CLI menu.

**Luồng chính:**

1. Mở hộp thoại chọn thư mục native của hệ điều hành.
2. User điều hướng và chọn thư mục mong muốn.
3. Chương trình lưu đường dẫn vào file config (`config.json` hoặc tương đương).
4. Hiển thị xác nhận: `Thư mục lưu: C:\Users\<Tên_User>\Downloads\SocialPeta_Downloader`
5. Tất cả file tải về từ lúc này được lưu vào thư mục đó.
6. Hệ thống thực hiện ngắt kết nối database cũ và gọi `UC-F02` để thiết lập cơ sở dữ liệu mới tại thư mục vừa được chọn.

**Ngoại lệ:**

- `UC-F01a` User đóng hộp thoại không chọn gì → giữ nguyên thư mục cũ, không thay đổi
- `UC-F01b` Thư mục được chọn không có quyền ghi → cảnh báo ngay, mở lại hộp thoại
- `UC-F01c` Đường dẫn quá dài (Windows giới hạn 260 ký tự) → cảnh báo, gợi ý chọn đường dẫn ngắn hơn
- `UC-F01d` Ổ đĩa được chọn không đủ dung lượng → cảnh báo kèm dung lượng còn trống, vẫn cho phép chọn

---

## UC-F02 — Đồng bộ Workspace và cơ sở dữ liệu SQLite

**Trigger:** Gọi sau khi `UC-F01` hoàn tất đổi thư mục thành công.

**Luồng chính:**

1. Hệ thống tìm kiếm tệp `db.sqlite3` trong thư mục tải xuống mới:
   - *Nếu chưa tồn tại:* Tạo mới tệp `db.sqlite3` tại đó và chạy migration để tạo các bảng dữ liệu.
   - *Nếu đã tồn tại:* Kết nối tới tệp database cũ này để khôi phục lịch sử tải xuống.
2. Cập nhật cache lưu trữ các tệp đã tải (vân tay dHash, MD5) từ database mới để phục vụ tính năng lọc trùng lặp.
3. Xuất file `download_info.csv` cập nhật tại thư mục mới nếu database chứa lịch sử tải.
4. Trả về trạng thái sẵn sàng làm việc cho giao diện.

**Ngoại lệ:**
- `UC-F02a` File database bị hỏng (corrupt) → Đổi tên file hỏng thành `.corrupt` và khởi tạo lại database mới trống, ghi log cảnh báo.
- `UC-F02b` Lỗi lock file do thư mục nằm trên USB hoặc NAS (không ghi được WAL mode) → Fallback SQLite sang chế độ ghi đồng bộ không cần WAL.

---

**Về implementation**, Python có sẵn thư viện cho việc này, không cần cài thêm gì:

```python
import tkinter as tk
from tkinter import filedialog

def pick_folder() -> str | None:
    root = tk.Tk()
    root.withdraw()          # ẩn cửa sổ Tk chính
    root.attributes("-topmost", True)  # hộp thoại hiện trên cùng
    folder = filedialog.askdirectory(title="Chọn thư mục lưu video")
    root.destroy()
    return folder or None    # None nếu user bấm Cancel
```

`tkinter` có sẵn trong Python standard library, chạy được trên cả Windows, macOS, Linux — mở đúng file explorer native của từng hệ điều hành mà không cần thư viện ngoài.
