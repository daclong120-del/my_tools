import os
import sys
import time
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def navigate_to_page(core, page, page_num: int) -> bool:
    """
    Hàm điều hướng trang dựa trên quy tắc chuẩn hóa:
    - Nếu trang <= 5: Click trực tiếp nút số trang.
    - Nếu trang > 5: Sử dụng Quick Jumper để nhập số trang rồi ấn Enter.
    """
    # Cuộn xuống cuối trang để nạp phần Pagination vào Viewport
    try:
        page.keyboard.press("End")
        time.sleep(1.0)
    except Exception:
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

    # Nhấn Escape để đóng các hộp thoại popup modal che khuất nút phân trang (nếu có)
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    # Gọi các helper phân trang có sẵn từ core.utils_service
    if page_num <= 5:
        success = core.utils_service._click_page_button(page, page_num)
    else:
        success = core.utils_service._jump_to_page(page, page_num)
        
    return success

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    print("[*] Đang kết nối tới Chrome debug port...")
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print("[-] Không kết nối được Chrome debug port 9222. Vui lòng mở Chrome debug trước.")
        return
        
    print("[*] Kích hoạt và đưa Chrome lên màn hình chính (foreground)...")
    core.utils_service.bring_chrome_to_foreground()
    
    print("[*] Đang quét tìm các tab SocialPeta hoạt động...")
    active_tabs = core.detect_tabs(port)
    if not active_tabs:
        print("[-] Không tìm thấy tab SocialPeta nào. Vui lòng mở trang và đăng nhập trước.")
        return
        
    tab_info = active_tabs[0]
    tab_index = tab_info["index"]
    tab_id = tab_info["tab_id"]
    print(f"[+] Đã phát hiện Tab [{tab_index}]: {tab_info['title']}")
    
    with sync_playwright() as p:
        print(f"[*] Đang kết nối Playwright qua CDP cổng {port}...")
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]
        
        # Ép đồng bộ hóa danh sách target của Playwright
        temp_page = context.new_page()
        temp_page.close()
        
        # Tìm page object qua tab_id
        page = core.tab_scanner._find_page_by_id(context, tab_id)
        if not page:
            print("[-] Không thể tìm thấy đối tượng Page tương ứng với tab.")
            return
            
        page.set_default_timeout(10000)
        page.bring_to_front()
        
        # === CHU KỲ 1: DI CHUYỂN TỪ TRANG 1 -> TRANG 20 ===
        print("\n=== [1] Bắt đầu điều hướng từ Trang 1 đến Trang 20 ===")
        for p_num in range(1, 21):
            print(f"[*] Đang chuyển đến Trang {p_num}...")
            ok = navigate_to_page(core, page, p_num)
            if ok:
                print(f"[+] Thành công chuyển sang Trang {p_num}")
                time.sleep(3.0)  # Chờ dữ liệu tải
            else:
                print(f"[-] Thất bại chuyển sang Trang {p_num}")
                
        # === CHU KỲ 2: DI CHUYỂN TỪ TRANG 20 -> TRANG 2 ===
        print("\n=== [2] Bắt đầu quay ngược từ Trang 20 về Trang 2 ===")
        for p_num in range(20, 1, -1):
            print(f"[*] Đang chuyển ngược về Trang {p_num}...")
            ok = navigate_to_page(core, page, p_num)
            if ok:
                print(f"[+] Thành công chuyển sang Trang {p_num}")
                time.sleep(3.0)  # Chờ dữ liệu tải
            else:
                print(f"[-] Thất bại chuyển sang Trang {p_num}")
                
        print("\n[+] Đã hoàn tất quy trình test chuyển trang.")
        browser.close()

if __name__ == "__main__":
    main()
