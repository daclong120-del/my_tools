# Kế hoạch triển khai SocialPeta Downloader - CLI V2

Tài liệu này đặc tả kế hoạch xây dựng giao diện dòng lệnh mới (CLI V2) với định hướng giao diện Terminal User Interface (TUI) cao cấp theo phong cách của Claude Code CLI, hỗ trợ tương tác hoàn toàn bằng phím mũi tên và tích hợp sâu cơ chế đồng bộ tải/cào 3 luồng song song.

## User Review Required

> [!IMPORTANT]
> **Các điểm lưu ý quan trọng trong CLI V2:**
> 1. **Cấu hình In-memory**: Mọi thiết lập (Thư mục tải mặc định được tự động nhận diện dựa trên thư mục `Downloads` của người dùng như `C:\Users\<Tên_User>\Downloads\SocialPeta_Downloader`, Cổng debug Chrome `9222`, và Số luồng video song song `3`) sẽ chỉ được lưu trữ tạm thời trong RAM khi chương trình chạy, không ghi đè hay cập nhật vào file `config.json` vật lý.
> 2. **Phím nóng dừng an toàn (Ctrl + Q)**: Cho phép kết thúc an toàn tiến trình cào và dọn dẹp thư mục tạm `.tmp` bất cứ lúc nào trong khi Dashboard cào đang chạy.
> 3. **Loại bỏ API Server**: CLI V2 là một TUI hoàn toàn độc lập, loại bỏ hoàn toàn việc khởi chạy FastAPI server (`api.py`).

## Open Questions

*Không có.* Kế hoạch được xây dựng trực tiếp dựa trên sự thống nhất và đặc tả trong `design_v2.md` và các chỉ thị của người dùng.

## Proposed Changes

---

### Core Downloader & Sniffer Filters

Bổ sung bộ lọc chế độ tải vào tầng nghiệp vụ để kiểm soát tài nguyên tải về dựa trên chế độ người dùng đã cấu hình.

#### [MODIFY] [sniffer.py](file:///d:/Python/my_tools/tools/socialpeta_downloader/core/sniffer.py)
- Tích hợp bộ lọc chế độ tải `download_mode` (lấy từ context) trong hàm `_process_api_response_for_tab`.
- Tránh đưa các tài nguyên không phù hợp vào queue tải hoặc queue YouTube click.

#### [MODIFY] [downloader.py](file:///d:/Python/my_tools/tools/socialpeta_downloader/core/downloader.py)
- Tích hợp bộ lọc chế độ tải `download_mode` trong `_download_worker` như một chốt chặn bảo vệ thứ hai.

---

### CLI V2 Terminal Interface

#### [NEW] [cli.py](file:///d:/Python/my_tools/tools/socialpeta_downloader/cli/cli_v2/cli.py)
- Triển khai toàn bộ giao diện CLI V2 độc lập.
- Sử dụng `InquirerPy` hoặc giải pháp bắt phím mũi tên thủ công (hoặc `questionary` / `inquirer`) cho menu tương tác.
- Tích hợp `pyfiglet` vẽ chữ **SOCIALPETA** lớn màu Cyan/Blue nổi bật ở đầu CLI.
- Triển khai menu chính và các menu con:
  - **1. Chọn trang tải**: Quét tab SocialPeta qua `core.detect_tabs(port)`. Khi chọn một tab:
    - Hiển thị menu Chọn loại tài nguyên: (1) Tải tất cả, (2) Chỉ tải ảnh, (3) Chỉ tải video YouTube, (4) Quay lại.
    - Mở Folder Explorer (`tkinter.filedialog`) để chọn thư mục lưu (In-memory).
    - Hỏi số lượng trang muốn tải.
    - Khởi chạy cào & tải song song.
  - **2. Mở thư mục tải**: Gọi `os.startfile(download_dir)` trên Windows để mở Folder Explorer.
  - **3. Cài đặt hệ thống**: Cho phép sửa đổi số luồng tải, thư mục lưu, cổng debug Chrome (tất cả chỉ thay đổi in-memory).
  - **4. Thoát chương trình**: Đóng hệ thống và thoát.
- Luồng xử lý sự cố trình duyệt Chrome: Nếu cổng debug không phản hồi, hiển thị menu 3 lựa chọn (Khởi động lại trình duyệt, Thử kết nối lại, Đóng chương trình).
- Chế độ hiển thị Dashboard cào/tải thời gian thực bằng `rich.live` và `rich.progress`.
- Bắt phím nóng `Ctrl + Q` để dừng an toàn tiến trình cào và tải.

#### [NEW] [run.bat](file:///d:/Python/my_tools/tools/socialpeta_downloader/cli/cli_v2/run.bat)
- Tệp tin script chạy nhanh CLI V2 bằng cách gọi môi trường Python ảo `.venv`.

---

## Verification Plan

### Automated Tests
- Chạy trực tiếp CLI V2 bằng python:
  ```bash
  .venv\Scripts\python.exe tools/socialpeta_downloader/cli/cli_v2/cli.py
  ```
- Kiểm tra tính tương thích của phím tắt `Ctrl + Q` và việc cài đặt thư viện cần thiết.

### Manual Verification
- Kiểm tra điều hướng phím mũi tên LÊN/XUỐNG trong menu CLI.
- Thử ngắt kết nối Chrome (đóng Chrome thủ công) và kiểm tra xem CLI có hiển thị menu xử lý sự cố tương ứng hay không.
- Kiểm tra chế độ lọc tải: Thử chọn "Chỉ tải ảnh" và kiểm tra xem hệ thống có bỏ qua tải video CDN và click YouTube hay không.
