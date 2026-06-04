import os
import sys
import time
from playwright.sync_api import sync_playwright

# Add workspace root to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.config import settings

def run_navigation_test(port: int = None):
    if port is None:
        port = settings.CHROME_DEBUG_PORT

    print(f"[*] Khoi tao core engine...")
    core = SocialPetaDownloaderCore()
    
    print(f"[*] Dang kiem tra va ket noi Chrome Debug Port: {port}...")
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print(f"[-] Khong the mo hoac ket noi toi Chrome debug port {port}.")
        return

    print(f"[*] Dang do tim cac tab SocialPeta dang mo...")
    active_tabs = core.detect_tabs(port)
    if not active_tabs:
        print("[-] Khong tim thay tab SocialPeta nao. Vui long mo trang Web SocialPeta truoc.")
        return

    # Use first detected tab for testing
    target_tab = active_tabs[0]
    tab_index = target_tab["index"]
    tab_id = target_tab["tab_id"]
    print(f"[+] Su dung tab test: Index={tab_index} | Title='{target_tab['title']}'")

    print("[*] Ket noi Playwright toi Chrome qua CDP...")
    with sync_playwright() as p:
        try:
            # We connect to debug port
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=5000)
            context = browser.contexts[0]
            
            # Find the page
            page = core.tab_scanner._find_page_by_id(context, tab_id)
            if not page:
                print("[-] Khong the lien ket toi doi tuong page cua tab.")
                return

            page.bring_to_front()
            
            # Loop page 1 to 20
            print("\n" + "="*50)
            print(" BAT DAU CHAY THU NGHIEM DIEU HUONG TU TRANG 1 -> 20 ")
            print("="*50)
            
            for page_num in range(1, 21):
                print(f"\n[*] Dang chuyen den Trang {page_num}...")
                
                # Scroll down to make sure pagination buttons are visible
                try:
                    page.keyboard.press("End")
                    time.sleep(0.5)
                except Exception:
                    pass
                
                success = False
                if page_num <= 5:
                    success = core.utils_service._click_page_button(page, page_num)
                else:
                    success = core.utils_service._jump_to_page(page, page_num)
                
                if success:
                    print(f"[+] Chuyen trang thanh cong: Dang o Trang {page_num}")
                    time.sleep(2.0)
                else:
                    print(f"[-] LOI: Khong the chuyen sang Trang {page_num}")
                    time.sleep(1.0)
            
            print("\n" + "="*50)
            print(" THU NGHIEM HOAN TAT ")
            print("="*50)

        except Exception as e:
            import traceback
            print(f"[-] Da xay ra loi trong qua trinh test: {e}\n{traceback.format_exc()}")
        finally:
            if 'browser' in locals() and browser:
                try:
                    browser.close()
                except Exception:
                    pass

if __name__ == "__main__":
    port_val = settings.CHROME_DEBUG_PORT
    if len(sys.argv) > 1:
        try:
            port_val = int(sys.argv[1])
        except ValueError:
            pass
    run_navigation_test(port_val)
