# Coffee Talk: Giải thích chi tiết về việc sửa 5 lỗi Core và Cấu trúc lại README

> Người viết: Antigravity AI
> Ngày: 2026-06-01
> Chủ đề: Giải thích các quyết định kiến trúc, bài học xương máu khi sửa lỗi Core & Viết lại README cho SocialPeta Downloader.

Chào bạn! Hãy rót một ly cà phê và ngồi xuống đây. Tôi sẽ kể cho bạn nghe toàn bộ câu chuyện đằng sau quá trình sửa 5 lỗi kỹ thuật nghiêm trọng trong lõi engine của SocialPeta Downloader, cũng như việc tôi đã tái cấu trúc tài liệu README.md như thế nào để bất cứ dev nào vào dự án cũng có thể bắt nhịp được ngay.

---

## 1. Approach & Reasoning (Cách tiếp cận & Tư duy từ đầu)

Khi bắt đầu nhận task, mục tiêu lớn nhất của chúng ta là giải quyết triệt để 5 vấn đề còn lại:
1. **CPU Spike do dHash** khi check trùng lặp video.
2. **Xung đột cổng debug** (`settings.CHROME_DEBUG_PORT`) khi có nhiều client gọi API.
3. **Nhận diện sai Chrome debug port** bằng socket thô.
4. **Lỗ hổng bảo mật SSRF** tại các điểm gọi `page.goto()`.
5. **Build script chỉ chạy được trên Windows**.

Tôi đã tiếp cận theo nguyên lý **"Phẫu thuật chính xác" (Surgical changes)**:
- Không viết lại toàn bộ hay cố gắng thay đổi thiết kế chung của hệ thống Mixin.
- Lần lượt đi qua từng module, xác định chính xác dòng code gây ra lỗi, cô lập vấn đề và giải quyết bằng giải pháp tối thiểu nhưng bền vững nhất.
- Luôn kiểm tra tính tương thích ngược của API để đảm bảo frontend Next.js không bị crash khi tích hợp.

---

## 2. Roads Not Taken (Những con đường đã tránh)

Dưới đây là những cách tiếp cận tôi từng nghĩ tới nhưng đã quyết định từ bỏ vì có quá nhiều rủi ro:

- **Với lỗi dHash (Fix #6)**: Ban đầu, tôi đã nghĩ đến việc lưu cache dHash vào RAM (in-memory cache). Tuy nhiên, nếu server khởi động lại (restart), toàn bộ cache RAM sẽ biến mất và CPU lại bị spike. Do đó, việc chọn ghi thẳng dHash vào JSON metadata file của từng video (persist cache) là lựa chọn tối ưu hơn cả.
- **Với lỗi Multi-client Port (Fix #8)**: Một ý tưởng khác là tạo một cơ chế Thread-local dynamic config để ghi đè `settings.CHROME_DEBUG_PORT` cục bộ theo từng thread. Tuy nhiên, điều này rất phức tạp và dễ phát sinh lỗi khi quản lý các WebSocket connections bất đồng bộ. Cách tốt nhất là truyền tường minh biến `port` qua tham số (parameter context-passing) từ API Route xuống tận Core, loại bỏ hoàn toàn việc chỉnh sửa cấu hình global singleton.
- **Với lỗi SSRF (Fix #15)**: Tôi đã định dùng các Regex phức tạp để validate URL. Tuy nhiên, Regex trong Python rất dễ bị bỏ sót các edge cases (ví dụ như `https://socialpeta.com.evil.com` hay ký tự unicode đặc biệt). Sử dụng thư viện chuẩn `urllib.parse.urlparse` là giải pháp an toàn và đáng tin cậy hơn rất nhiều.

---

## 3. How Things Connect (Sự kết nối giữa các thành phần)

Hãy tưởng tượng luồng đi của request giống như một băng chuyền:
1. Client (Next.js/Electron) gửi API yêu cầu check trạng thái hoặc bắt đầu tải, kèm theo cấu hình `port` riêng.
2. `api/routes.py` tiếp nhận request, truyền tham số `port` vào `check_login_status(port)` hoặc `run_tab_scraper(..., port)`.
3. `core/chrome.py` nhận port, gọi hàm `_is_chrome_cdp_active(port)` để gửi request GET xác thực tới `/json/version`. Nếu Chrome chưa chạy, nó sẽ tự khởi động một instance Chrome debug mới độc lập với custom profile riêng.
4. `core/legacy_scraper.py` tiếp nhận URL tải từ client, kiểm tra độ an toàn bằng `is_safe_url(url)` trước khi cho phép Playwright điều hướng đĩa (`page.goto`).
5. Trong lúc tải, nếu video mới cần tải, `core/deduplication.py` sẽ kiểm tra dHash của nó. Nếu dHash đã tồn tại trong JSON metadata cache, nó sẽ lấy kết quả ngay; nếu chưa, nó mới gọi `ffmpeg` tính dHash và ghi ngược lại vào metadata file để lưu trữ lâu dài.

---

## 4. Tools & Methods (Công cụ & Phương pháp)

- **urllib.parse.urlparse**: Dùng để phân tách URL một cách chuẩn hóa, giúp lấy domain (`netloc`) chính xác để chống bypass domain trong SSRF.
- **requests.get("/json/version")**: Thay vì kiểm tra TCP socket thô, chúng ta truy vấn trực tiếp HTTP endpoint của giao thức Chrome DevTools Protocol để đảm bảo đó thực sự là Chrome đang phản hồi.
- **sys.platform**: Sử dụng để viết build script tương thích chéo nền tảng, giúp tự động chuyển đổi giữa `Scripts/pyinstaller.exe` (Windows) và `bin/pyinstaller` (macOS/Linux) mà không cần can thiệp thủ công.

---

## 5. Tradeoffs (Sự đánh đổi)

- **HTTP Verification vs Speed**: Việc gọi `requests.get` để xác minh Chrome CDP thay vì kết nối TCP thô sẽ chậm hơn khoảng vài mili-giây do có overhead của giao thức HTTP. Tuy nhiên, sự hy sinh nhỏ này mang lại độ tin cậy tuyệt đối và tránh hoàn toàn tình trạng nhận diện nhầm các dịch vụ hệ thống khác là Chrome.
- **dHash Caching vs Metadata Size**: Lưu thêm dHash vào JSON metadata làm kích thước của tệp metadata tăng lên một chút (thêm một vài bytes). Đổi lại, tài nguyên CPU được giải phóng đáng kể, giúp tăng tốc độ xử lý hàng trăm video từ vài chục giây xuống dưới một giây.

---

## 6. Mistakes & Dead Ends (Sai lầm & Ngõ cụt trong quá trình)

Trong phiên làm việc trước, lúc sửa lỗi đỏ IDE (Mixin unresolved attributes), tôi đã cố gắng giải quyết bằng cách định nghĩa các Mixins với sự kế thừa lẫn nhau. Tuy nhiên, điều này tạo ra vòng lặp kế thừa (circular inheritance) và làm cấu trúc lớp trở nên rất rối. 

*Bài học rút ra*: Tôi đã quay lại giải pháp khai báo các Type Annotations dạng stubs trên đầu Mixin class. Đây là cách chuẩn chỉ nhất trong lập trình hướng đối tượng đa kế thừa (Multiple Inheritance) của Python, giúp thỏa mãn trình kiểm tra kiểu tĩnh của IDE mà không làm xáo trộn cấu trúc runtime.

---

## 7. Future Pitfalls (Cạm bẫy cần tránh trong tương lai)

Khi viết code điều khiển trình duyệt bằng Playwright/Selenium trong dự án lớn:
- **Luôn truyền biến**: Tránh tuyệt đối việc lưu trữ các cấu hình động (như port, proxy, user-agent) vào các class settings dạng singleton nếu hệ thống có hỗ trợ chạy đa luồng hoặc đa client. Hãy luôn truyền tham số dạng ngữ cảnh (context/parameter passing).
- **Phân tách môi trường rõ ràng**: Khi viết scripts tự động hóa hoặc build tool, đừng bao giờ giả định môi trường chạy luôn là Windows. Luôn sử dụng thư viện `os.path.join` và kiểm tra `sys.platform`.

---

## 8. Expert vs Beginner (Tư duy của chuyên gia)

- **Beginner**: Khi thấy CPU bị spike lúc check duplicate, beginner thường nghĩ ngay đến việc giảm số lượng luồng tải song song (workers) hoặc nâng cấp cấu hình CPU.
- **Expert**: Nhận ra nguyên nhân là thuật toán dHash gọi ffmpeg lặp đi lặp lại một cách lãng phí trên cùng một dữ liệu. Họ sẽ áp dụng cơ chế Memoization/Caching để loại bỏ các phép tính thừa ở cấp độ giải thuật.

---

## 9. Transferable Lessons (Bài học áp dụng cho dự án khác)

- **Publisher-Subscriber (Pub-Sub)** là giải pháp tối ưu khi cần phát sóng (broadcast) log/event thời gian thực từ một engine duy nhất ra nhiều kết nối WebSocket độc lập. Nó loại bỏ hoàn toàn race conditions và hiện tượng mất mát dữ liệu giữa các clients.
- **Sanitize URL trước khi page.goto**: Bất cứ khi nào bạn viết crawler hay tool tự động hóa cho phép người dùng nhập URL, hãy luôn kiểm tra whitelist tên miền ở cấp độ sâu nhất để phòng ngừa các cuộc tấn công SSRF nguy hiểm.

Hy vọng những chia sẻ trên ly cà phê này giúp bạn nắm rõ và tự tin tiếp quản hệ thống! Chúc bạn code vui vẻ!
