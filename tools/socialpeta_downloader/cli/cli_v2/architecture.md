# CLI V2 - Kiến trúc & Nguyên lý hoạt động

Tài liệu này giải thích chi tiết về nguyên lý hoạt động của SocialPeta Downloader CLI V2, bao gồm vòng đời của một phiên làm việc (Session) và cơ chế trích xuất link YouTube tự động không bỏ sót.

---

## 1. Vòng đời của một phiên làm việc (Session Lifecycle)

CLI V2 hoạt động theo cơ chế **In-memory Configuration** (Cấu hình trên RAM) và tương tác bằng phím mũi tên. Mọi thay đổi về cấu hình chỉ tồn tại trong suốt quá trình chạy của phiên hiện tại và không ghi đè vào các file cấu hình vật lý.

### Quy trình hoạt động của CLI:

1. **Khởi chạy và kết nối Chrome Debug Port**:
   - Khi CLI được khởi chạy, nó nạp cấu hình mặc định:
     - Thư mục tải xuống: `D:\Downloads\SocialPeta_Workspace`
     - Cổng gỡ lỗi Chrome (Chrome Debug Port): `9222`
     - Số luồng tải video song song: `3`
   - Gọi lớp `ChromeService` để kiểm tra xem cổng `9222` đã mở chưa.
   - Nếu cổng chưa mở, hệ thống tìm kiếm trình duyệt Google Chrome trên máy (Registry Windows hoặc các đường dẫn chuẩn) và tự động khởi chạy Chrome với tham số `--remote-debugging-port=9222` và thư mục profile riêng `chrome_debug_profile`.

2. **Xử lý sự cố kết nối Chrome (Chrome Trouble-shooting)**:
   - Nếu sau 5 giây không thể kết nối tới Chrome, chương trình không bị crash mà sẽ hiển thị menu xử lý sự cố gồm 3 tùy chọn:
     1. *Chọn khởi động lại trình duyệt với port đó*: Cố gắng tắt và khởi chạy lại Chrome trên cổng tương ứng.
     2. *Thử kết nối lại*: Kiểm tra lại trạng thái cổng một lần nữa (dành cho trường hợp người dùng mở Chrome thủ công chậm).
     3. *Đóng chương trình*: Thoát an toàn.

3. **Chọn trang tải (Tab Selection)**:
   - Hệ thống quét danh sách các tab đang mở trong Chrome qua CDP (Chrome DevTools Protocol) HTTP endpoint (`http://127.0.0.1:9222/json/list`).
   - Lọc ra các tab có URL khớp với SocialPeta hoặc Guangdada.
   - Hiển thị danh sách tiêu đề các tab lên CLI để người dùng di chuyển phím mũi tên LÊN/XUỐNG và nhấn `Enter` để chọn.

4. **Cấu hình phiên cào/tải**:
   - Người dùng chọn chế độ lọc tải:
     1. *Tải tất cả các loại*: Tải cả ảnh, video CDN, và video YouTube.
     2. *Chỉ tải ảnh*: Bỏ qua các tác vụ video, chỉ tải ảnh/thumbnail quảng cáo.
     3. *Chỉ tải video youtube*: Chỉ tải các quảng cáo chạy nguồn YouTube.
   - Chọn thư mục lưu: Chương trình mở hộp thoại hệ thống **Folder Explorer** (`tkinter.filedialog.askdirectory`) để người dùng dễ dàng chọn thư mục lưu (giá trị này ghi đè in-memory vào `context.download_dir`).
   - Nhập số lượng trang cần cào.

5. **Khởi chạy luồng song song (3-Stream parallel execution)**:
   - Sau khi bắt đầu chạy, CLI gọi `start_system` của Core Downloader để kích hoạt 3 luồng hoạt động độc lập:
     - **Stream 1 (Scraper/Sniffer - Luồng Cào/Phát hiện)**: Tự động cuộn trang, chuyển trang và click nút chuyển trang trên Chrome qua Playwright CDP. Luồng này bắt gói tin API trả về từ SocialPeta chứa metadata quảng cáo.
     - **Stream 2 (Downloader - Luồng Tải)**: Chạy nhiều worker song song (mặc định 3 luồng). Nó lấy các ad từ hàng đợi `pending_downloads` để tải ảnh/video CDN hoặc tải video YouTube qua `yt-dlp`.
     - **Stream 3 (Deduplication - Luồng Lọc trùng)**: Lắng nghe hàng đợi `filter_queue` của các video đã tải về dạng tạm thời. Sử dụng `ffmpeg` & `ffprobe` băm MD5 và so sánh vân tay video (phát hiện trùng lặp nâng cao). Nếu không trùng, đổi tên sang file unique lưu vào thư mục đích.
   - CLI hiển thị **Live Dashboard** cập nhật liên tục tiến độ: Số lượng đã sniff, đang tải, thành công, thất bại, trùng lặp và tiến trình tải của các luồng.

6. **Phím tắt thoát an toàn (Safe Exit Key)**:
   - Khi Dashboard đang chạy, người dùng có thể nhấn tổ hợp phím **`Ctrl + Q`** bất kỳ lúc nào để kích hoạt dừng khẩn cấp. Chương trình sẽ dừng mọi luồng cào/tải, dọn dẹp thư mục tạm `.tmp` và đưa người dùng trở lại Menu chính.

---

## 2. Cơ chế lấy hết link YouTube không bỏ sót

Đối với các quảng cáo SocialPeta chạy nguồn YouTube (thường có duration là `0s` hoặc không chứa link video CDN trực tiếp trong payload phản hồi API), CLI V2 áp dụng cơ chế Click chi tiết và Truy tìm link nhúng tự động như sau:

### Quy trình trích xuất chi tiết:

1. **Phân loại trạng thái ban đầu (`youtube_click_required`)**:
   - Khi gói tin API từ SocialPeta được sniff, lớp `UtilsService` phân tích metadata của ad.
   - Nếu phát hiện quảng cáo này chạy trên nền tảng YouTube (`platform == "youtube"` hoặc chứa từ khóa youtube trong trường publisher/youtube_url) nhưng **chưa có link YouTube trực tiếp** trong phản hồi API (thường là link CDN trống hoặc video 0s), ad này được gán `media_type = "youtube_click_required"`.
2. **Hàng đợi xử lý YouTube của từng Tab (`tab_youtube_queues`)**:
   - Thay vì bỏ qua, Sniffer đẩy ad này vào hàng đợi của tab tương ứng `self.context.tab_youtube_queues[tab_index]`.
   - Ngay sau khi Sniffer hoàn thành việc cuộn và tải hết ảnh trên trang hiện tại, nó sẽ kiểm tra hàng đợi này. Nếu phát hiện có ad cần click YouTube, nó sẽ kích hoạt luồng trích xuất.
3. **Mô phỏng click chi tiết và truy vết (UC-03 click flow)**:
   - `YoutubeService` sử dụng JavaScript evaluate chạy trực tiếp trong trang tab để tìm đúng card quảng cáo tương ứng (bằng cách so sánh mã hash của ảnh cover/ảnh thumbnail của ad).
   - Khi tìm thấy card, nó tự động cuộn card đó vào giữa màn hình (`scrollIntoView`) và click mở modal chi tiết của ad đó.
   - Khi modal chi tiết mở ra, hệ thống liên tục poll (quét định kỳ mỗi 500ms, tối đa 3-6 giây) để tìm:
     - Thẻ neo `a` trỏ đến `youtube.com` hoặc `youtu.be` trong modal.
     - Thẻ `iframe` nhúng trình phát video YouTube để lấy thuộc tính `src`.
     - Regex tìm link YouTube thô trong text modal.
4. **Chuẩn hóa và Tải về**:
   - Khi lấy được link YouTube, link sẽ được chuẩn hóa về dạng chuẩn `https://www.youtube.com/watch?v=VIDEO_ID`.
   - Trạng thái ad được cập nhật thành `youtube_video`, và ad được đẩy sang hàng đợi `pending_downloads` để luồng Downloader gọi `yt-dlp` tải xuống video chất lượng cao.
   - Sau khi hoàn thành hoặc thất bại, hệ thống gửi phím nóng `Escape` để đóng modal chi tiết và tiếp tục xử lý ad tiếp theo trong hàng đợi.

---

## 3. Bản đồ cấu trúc thư mục CLI V2

```text
tools/socialpeta_downloader/cli/cli_v2/
├── architecture.md       # Tài liệu kiến trúc và luồng chạy (File này)
├── cli.py                # Điểm chạy giao diện dòng lệnh V2 chính
└── run.bat               # File script Windows để khởi chạy nhanh CLI V2
```
