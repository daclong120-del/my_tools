---
name: navigation-tab-control
description: "Guide for managing active Chrome tabs, bringing windows to foreground, and implementing robust multi-page navigation in SocialPeta."
category: automation
triggers: navigation, tab-control, page-navigation, pagination, quick-jumper, chrome-cdp
---

# Hướng dẫn Điều hướng và Chuyển đổi Tab (Chrome CDP)

Tài liệu này hướng dẫn cách sử dụng các thành phần core trong hệ thống để thực hiện kết nối, phát hiện tab SocialPeta, đưa cửa sổ trình duyệt lên tiền cảnh (foreground), và thực hiện vòng lặp điều hướng trang đáng tin cậy (từ Trang 1 đến Trang 20).

---

## 1. Các thành phần Core liên quan (Core Components)

Hệ thống cung cấp các dịch vụ core giúp kiểm soát trình duyệt qua Chrome DevTools Protocol (CDP):

- **`ChromeService`** (`core/chrome.py`): Khởi chạy và quản lý cổng remote debugging (mặc định: `9222`) với các cờ (flags) tối ưu chống đóng băng tab.
- **`TabScanner`** (`core/tab_manager.py`): 
  - `core.detect_tabs(port)`: Tìm kiếm nhanh các tab đang mở qua HTTP endpoint `/json/list` mà không gây rò rỉ phiên kết nối.
  - `core.tab_scanner._find_page_by_id(context, tab_id)`: Liên kết một `tab_id` cụ thể với đối tượng `Page` thực tế của Playwright.
- **`UtilsService`** (`core/utils.py`):
  - `core.utils_service.bring_chrome_to_foreground()`: Chạy lệnh PowerShell nền để tìm và kích hoạt cửa sổ Google Chrome hiển thị lên màn hình chính, ngăn chặn Windows tạm dừng (freeze/occlude) luồng JavaScript của tab.

---

## 2. Quy trình 4 bước điều khiển và điều hướng

### Bước 1: Khởi tạo Core và Kích hoạt Trình duyệt
Gọi `ensure_chrome_debug_port` để đảm bảo cổng debug hoạt động. Sau đó chạy `bring_chrome_to_foreground` để mở khóa tối ưu hóa cửa sổ.

```python
from socialpeta_downloader.core import SocialPetaDownloaderCore

core = SocialPetaDownloaderCore()
port = 9222

# 1. Đảm bảo Chrome Debug Port đang mở
if not core.chrome_service.ensure_chrome_debug_port(port):
    raise Exception("Không thể mở hoặc kết nối cổng debug Chrome.")

# 2. Đưa Chrome lên màn hình chính (tránh treo tab chạy nền)
core.utils_service.bring_chrome_to_foreground()
```

### Bước 2: Dò tìm Tab và Lấy Page Object
Duyệt tìm tab SocialPeta đang hoạt động hoặc tự động tạo tab mới và đợi người dùng đăng nhập.

```python
from playwright.sync_api import sync_playwright

active_tabs = core.detect_tabs(port)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    context = browser.contexts[0]
    
    if not active_tabs:
        # Nếu chưa mở SocialPeta, tự động mở trang chủ và chờ đăng nhập
        page = context.new_page() if not context.pages else context.pages[0]
        page.goto("https://www.socialpeta.com")
        
        print("[!] Đang chờ người dùng đăng nhập và vào trang Tìm kiếm quảng cáo...")
        while True:
            # Nhận diện trang Ad Search qua sự xuất hiện của thanh phân trang
            if page.locator("li.ant-pagination-item-1, ul.el-pagination").count() > 0:
                print("[+] Đã phát hiện trang tìm kiếm quảng cáo!")
                break
            time.sleep(2.0)
    else:
        # Nếu đã có tab SocialPeta, kết nối trực tiếp bằng ID
        tab_id = active_tabs[0]["tab_id"]
        page = core.tab_scanner._find_page_by_id(context, tab_id)
        page.bring_to_front()
```

### Bước 3: Đưa cửa sổ Tab lên hàng đầu
Luôn gọi `page.bring_to_front()` trước khi bắt đầu thao tác trên trang.

```python
page.bring_to_front()
page.set_default_timeout(5000) # Thiết lập timeout tối đa 5s tránh treo vô hạn
```

### Bước 4: Thực thi Vòng lặp Điều hướng (Từ Trang 1 đến 20)
Trang tìm kiếm quảng cáo của SocialPeta (sử dụng Ant Design Pagination hoặc Element UI Pagination) có 2 cách điều hướng:
1. **Click trực tiếp nút số trang** (dành cho các trang đầu gần kề, thường là trang 1 đến 5).
2. **Sử dụng Quick Jumper** (dành cho trang ở xa, từ trang 6 đến 20) bằng cách nhập số vào ô Input và ấn `Enter`.

#### Thuật toán điều hướng chuẩn hóa:

```python
import time

def navigate_to_page(page, page_num: int) -> bool:
    # Cuộn xuống cuối trang để tải đầy đủ cấu trúc phân trang vào viewport
    try:
        page.keyboard.press("End")
        time.sleep(1.0)
    except Exception:
        pass

    # Quy tắc: Trang <= 5 click trực tiếp, Trang > 5 dùng Quick Jumper
    if page_num <= 5:
        # Danh sách selectors ưu tiên cho các nút trang trực tiếp
        selectors = [
            f"li.ant-pagination-item-{page_num}",
            f"ul.ant-pagination li.ant-pagination-item-{page_num}",
            f"ul.el-pagination li.number:has-text('{page_num}')",
            f"button:has-text('{page_num}')"
        ]
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.scroll_into_view_if_needed(timeout=1000)
                loc.click(timeout=2000)
                return True
    else:
        # Danh sách selectors ưu tiên cho ô nhập nhảy trang nhanh
        jumper_selectors = [
            ".ant-pagination-options-quick-jumper input",
            ".ant-pagination-options input",
            ".el-pagination__jump input"
        ]
        for sel in jumper_selectors:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.scroll_into_view_if_needed(timeout=1000)
                loc.click(timeout=1000)
                loc.fill(str(page_num))
                loc.press("Enter")
                return True
                
        # Fallback: Nếu không tìm thấy Quick Jumper, click nút Next trang
        next_selectors = ["li.ant-pagination-next", "button.btn-next"]
        for sel in next_selectors:
            next_btn = page.locator(sel).first
            if next_btn.count() > 0:
                next_btn.click(timeout=2000)
                return True
                
    return False

# Chạy vòng lặp test từ trang 1 đến 20
for p_num in range(1, 21):
    success = navigate_to_page(page, p_num)
    if success:
        print(f"[+] Điều hướng thành công đến Trang {p_num}")
        time.sleep(2.5) # Chờ dữ liệu bảng/video tải hoàn chỉnh
    else:
        print(f"[-] Thất bại khi điều hướng đến Trang {p_num}")
```

---

## 3. Lưu ý và Phòng ngừa rủi ro
1. **Lỗi treo CDP do occlusion**: Chrome sẽ dừng phản hồi lệnh CDP nếu cửa sổ trình duyệt bị thu nhỏ (minimize) hoặc bị che lấp hoàn toàn. Hãy luôn gọi `bring_chrome_to_foreground()` trước khi truy cập trang.
2. **Thiết lập Timeout**: Tuyệt đối không gọi các hàm hành động của Playwright không có timeout. Thiết lập `page.set_default_timeout(5000)` để ngăn chương trình bị treo vô hạn nếu mạng chậm hoặc trang web không tải kịp.
3. **Tránh click trùng lặp**: Các hành động gõ phím (`fill`) trên jumper input thỉnh thoảng cần được xóa dữ liệu cũ (gọi `loc.clear()` hoặc chọn toàn bộ văn bản trước khi fill) để tránh ghi đè số trang sai lệch.
