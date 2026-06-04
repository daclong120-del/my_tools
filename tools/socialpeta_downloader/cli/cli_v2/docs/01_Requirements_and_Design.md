# Yêu cầu và Thiết kế Giao diện (Requirements & Design)

Tài liệu này đặc tả các yêu cầu chức năng, phi chức năng, đối tượng người dùng và thiết kế giao diện dòng lệnh (TUI) của SocialPeta Downloader CLI V2.

---

## 1. Mục tiêu và Phạm vi dự án
* **Mục tiêu:** Tự động hóa quá trình thu thập tài nguyên quảng cáo (ảnh, video CDN, video YouTube ẩn) từ thư viện SocialPeta/Guangdada thông qua cơ chế cào dữ liệu Playwright CDP.
* **Phạm vi:** 
  - Hỗ trợ tải dữ liệu qua 3 luồng song song (Scraper, Downloader, Deduplicator).
  - Tích hợp công cụ lọc trùng lặp video dHash (FFmpeg).
  - Hoạt động độc lập dưới dạng file `.exe` giao diện TUI trên Windows, không yêu cầu cài đặt Python môi trường ngoài.

---

## 2. Đối tượng Người dùng (User Classes)

1. **Media Buyer / Ad Optimizer:**
   - Cần thu thập nhanh chóng hàng loạt quảng cáo để đánh giá xu hướng. 
   - Yêu cầu: Giao diện dễ dùng (chạy file `.bat`), không tải trùng lặp làm nhiễu dữ liệu.
2. **Designer / Video Editor:**
   - Sử dụng các tài nguyên tải về để chỉnh sửa, thiết kế lại thành mẫu quảng cáo mới (Creative Re-design).
   - Yêu cầu: Chất lượng video YouTube cao nhất (`yt-dlp`), ảnh tĩnh giữ nguyên gốc CDN không nén. Các tệp tin phân loại theo thư mục `{Tên_mạng_quảng_cáo}_{Tên_ứng_dụng}`.
3. **Developer / Admin:**
   - Vận hành, bảo trì, theo dõi hiệu năng và xử lý lỗi.
   - Yêu cầu: Ghi log chi tiết, code dễ bảo trì, giải phóng bộ nhớ (dọn dẹp `.temp_download`).

---

## 3. Các Use Case và Chế độ tải

Hệ thống hỗ trợ 3 chế độ tải chính (được lựa chọn ở màn hình TUI):

1. **Tải tất cả các loại (Tải full):** 
   - Hệ thống tiến hành cào và tải xuống *toàn bộ* Ảnh tĩnh, Video gốc CDN, và Video nguồn YouTube (truy tìm link qua click ẩn). Tất cả video tải về sẽ đi qua luồng lọc trùng lặp FFmpeg.
2. **Chỉ tải ảnh:**
   - **Đặc điểm:** Hệ thống bỏ qua hoàn toàn luồng click dò tìm video YouTube và bỏ qua việc lưu video CDN. Luồng Dedup bằng FFmpeg được *tắt* để tiết kiệm tài nguyên. Chỉ sử dụng hàm băm MD5 để lọc trùng ảnh tĩnh.
3. **Chỉ tải video YouTube:**
   - **Đặc điểm:** Hệ thống bỏ qua việc tải ảnh và video CDN thông thường. DOM Scanner chỉ tập trung nhận diện icon YouTube và kích hoạt luồng click truy tìm URL. 

---

## 4. Giao diện Terminal Mockup (TUI/UI Design)

Giao diện được thiết kế tương tác bằng phím mũi tên (Arrow keys) LÊN/XUỐNG và nhấn **Enter**. Các cấu hình (Số luồng tải, Thư mục tải, Chrome Port) lưu trữ **In-memory**, không can thiệp vào file cấu hình vật lý. Người dùng có thể nhấn **Ctrl + Q** bất cứ lúc nào để thoát an toàn và dọn dẹp thư mục tạm.
* **Lưu ý về Dialog Chọn Thư Mục:** Mặc dù là TUI, chương trình vẫn HỖ TRỢ mở cửa sổ "Folder Explorer" để người dùng chọn thư mục cho tiện. **TUY NHIÊN**, tuyệt đối KHÔNG sử dụng `Tkinter` hay các thư viện GUI Python nặng nề nào khác (để tránh lỗi `init.tcl` khi build Nuitka). Thay vào đó, sử dụng Native Windows API (thông qua `ctypes`) hoặc gọi script `PowerShell` ngầm để bật hộp thoại Folder Browser gốc của hệ điều hành.

### Màn hình Menu Chính
```text
███████╗ ██████╗  ██████╗██╗ █████╗ ██╗     ██████╗ ███████╗████████╗ █████╗ 
██╔════╝██╔═══██╗██╔════╝██║██╔══██╗██║     ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗
███████╗██║   ██║██║     ██║███████║██║     ██████╔╝█████╗     ██║   ███████║
╚════██║██║   ██║██║     ██║██╔══██║██║     ██╔═══╝ ██╔══╝     ██║   ██╔══██║
███████║╚██████╔╝╚██████╗██║██║  ██║███████╗██║     ███████╗   ██║   ██║  ██║
╚══════╝ ╚═════╝  ╚═════╝╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝   ╚═╝   ╚═╝  ╚═╝
(SocialPeta Video Downloader Engine - CLI Version 2.0)

? Hãy sử dụng phím mũi tên ↑↓ để chọn tính năng:
❯ 1. Chọn trang tải
  2. Mở thư mục tải
  3. Cài đặt hệ thống
  4. Thoát chương trình
```

### Màn hình Chọn loại tài nguyên (Áp dụng 3 Use Case)
```text
? Chọn loại tài nguyên bạn muốn tải về:
❯ 1. Tải tất cả các loại (Tải hết video CDN + YouTube + Ảnh, không bỏ sót)
  2. Chỉ tải ảnh (Chỉ tải toàn bộ ảnh của các quảng cáo, bỏ qua các bước xử lý video)
  3. Chỉ tải video youtube (Chỉ truy tìm và tải video từ nguồn YouTube)
  4. Quay lại
```

### Bảng Giám sát Trực quan (Live Dashboard)
```text
[+] Bắt đầu tiến trình cào và tải...
---------------------------------------------------------------------------------
[HỆ THỐNG] Threads: 3/3 active | CPU: 12.5% | RAM: 4.8 GB | Disk: OK (124 GB free)
[THỐNG KÊ] Tổng sniff: 84 | Chờ: 15 | Đang tải: 3 | Xong: 60 | Trùng: 5 | Lỗi: 1
---------------------------------------------------------------------------------

[ĐANG TẢI VIDEO]
- Ad #10029381: ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 100% [Done]
- Ad #10029385: ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░  50% [Tải CDN: 12.4 MB/s]
- Ad #10029386: ▓▓░░░░░░░░░░░░░░░░░░  10% [Tải YouTube: 2.1 MB/s]

[NHẬT KÝ HOẠT ĐỘNG (LOGS)]
21:40:02 [INFO] Đã phát hiện 24 ads mới từ Tab Shopee Ad Campaign
21:40:05 [WARN] Ad #10029383 bị trùng dHash với Ad #9991208 (Bỏ qua)
21:40:08 [INFO] Tải thành công video Ad #10029381 -> shopee_10029381.mp4
```

---

## 5. Luồng Tương tác Chi tiết (User Flow Wizard)

Tài liệu thiết kế trước đây chưa mô tả cụ thể luồng các bước từ khi người dùng chọn `1. Chọn trang tải`. Dưới đây là luồng đặc tả chi tiết (Wizard) khớp với thực tế logic của CLI:

### 5.1. Chức năng chính: `1. Chọn trang tải`
Khi người dùng bấm enter, hệ thống sẽ chạy qua 6 bước (Steps):
* **Bước 1: Kiểm tra kết nối Chrome Debug**
  - Hệ thống cố gắng ping Chrome CDP tại port đã cấu hình (mặc định 9222).
  - Nếu kết nối thất bại, hiển thị Menu xử lý sự cố (1. Khởi động lại Chrome bằng code / 2. Thử kết nối lại / 3. Thoát).
* **Bước 2: Quét Tab đang mở**
  - Liệt kê các tab SocialPeta đang hoạt động trong Chrome để người dùng chọn. Có chức năng **[R. Load lại]** nếu tab chưa xuất hiện.
* **Bước 3: Chọn Loại Tài nguyên**
  - Hiển thị bảng chọn 3 Mode như đã định nghĩa ở phần 3 (Tất cả / Chỉ ảnh / Chỉ YouTube).
* **Bước 4: Xác nhận / Thay đổi thư mục lưu**
  - Hệ thống gọi Native Dialog (PowerShell) để mở cửa sổ Folder Explorer trực quan. Người dùng có thể trỏ thư mục lưu. (Đường dẫn này được cập nhật In-memory ngay lập tức).
* **Bước 5: Nhập số lượng trang cần cào**
  - Trình cào (Scraper) yêu cầu người dùng nhập số nguyên tương ứng với số Page muốn tự động Next.
* **Bước 6: Kích hoạt Live Dashboard**
  - Bắt đầu tiến trình tải. Chặn input thường, hiện giao diện giám sát Real-time (phần 4). Lắng nghe phím `Ctrl + Q` để ngắt an toàn.

### 5.2. Chức năng phụ khác
* **`2. Mở thư mục tải`**: 
  - Gọi lệnh `os.startfile()` để bật cửa sổ File Explorer gốc của Windows, trỏ thẳng vào thư mục đã cấu hình để người dùng xem nhanh các file Media tải về.
* **`3. Cài đặt hệ thống`**:
  - Cho phép người dùng chỉnh sửa 3 tham số In-memory: (1) Số luồng tải đồng thời, (2) Thư mục tải mặc định (Sẽ gọi PowerShell Dialog), (3) Cổng Debug Port của Chrome. 
* **`4. Thoát chương trình`**: Thoát vòng lặp CLI và đóng app an toàn.
