# tools/socialpeta_downloader/core/legacy_sniffer.py
"""
Responsibility: Legacy single-tab sniffer worker and pagination loops.
"""

import time
import queue
import threading
from typing import Optional, Any
from playwright.sync_api import sync_playwright
from socialpeta_downloader.config import settings
from socialpeta_downloader.core.protocols import IEngineContext
from socialpeta_downloader.core.utils import is_socialpeta_url

class LegacySnifferService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def _process_api_response(self, data: dict):
        if not self.context:
            return
            
        target_pages = getattr(self.context, "pagination_target_pages", 0)
        current_page = getattr(self.context, "current_page", 1)
        if target_pages and target_pages > 0 and current_page > target_pages:
            self.context.page_packet_received.set()
            return
            
        try:
            items = self.context.utils_service._recursive_find_creatives(data)
            
            if not items:
                self.context.last_packet_empty = True
                print("[*] Sniffer: Nhan goi tin nhung danh sach trong.")
            else:
                self.context.last_packet_empty = False
                
            new_count = 0
            for raw_item in items:
                parsed = self.context.utils_service._parse_creative_item(raw_item)
                if not parsed["ad_id"]:
                    continue
                    
                status = self.context.ad_id_to_status.get(parsed["ad_id"])
                if status and status != "failed":
                    continue
                    
                if self.context.utils_service._is_ad_already_downloaded(parsed["ad_id"]):
                    continue

                if parsed["media_type"] == "image":
                    self.context.utils_service._save_item_state(parsed)
                    self.context.session_service.append_to_csv(parsed)
                    self.context.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                elif parsed["media_type"] in ("youtube_video", "youtube_thumbnail"):
                    self.context.utils_service._save_item_state(parsed)
                    self.context.session_service.append_to_csv(parsed)
                    self.context.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                elif parsed["media_type"] == "youtube_click_required":
                    print(f"[*] Phat hien quang cao YouTube (ID: {parsed['ad_id']}). Dang sap xep click de lay iframe...")
                    self.context.utils_service._save_item_state(parsed)
                    self.context.youtube_extract_queue.put(parsed)
                else:
                    self.context.utils_service._save_item_state(parsed)
                    self.context.session_service.append_to_csv(parsed)
                    self.context.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                    
            if new_count > 0:
                print(f"[+] Sniffer: Phat hien va xep hang {new_count} media moi.")
                
            self.context.page_packet_received.set()
        except Exception as e:
            print(f"[-] Sniffer error parsing creative list: {e}")
            self.context.page_packet_received.set()

    def stream_1_sniffer(self):
        """
        Stream 1 Thread. Handles Chrome CDP connection and Network Sniffing.
        """
        print("[*] Stream 1 (Sniffer) bat dau...")
        if not self.context:
            return
            
        while self.context.running:
            try:
                self.context.playwright_connected = False
                browser = None
                with sync_playwright() as p:
                    print(f"[*] Dang ket noi Chrome qua Debug Port {settings.CHROME_DEBUG_PORT}...")
                    try:
                        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{settings.CHROME_DEBUG_PORT}", timeout=2000)
                        context = browser.contexts[0]
                    except Exception as e:
                        print(f"\n[!] CANH BAO: Khong the ket noi Chrome Debug port {settings.CHROME_DEBUG_PORT}! ({e})")
                        print(f"[*] Vui long mo Chrome voi command: chrome.exe --remote-debugging-port={settings.CHROME_DEBUG_PORT}")
                        print("[*] Luong Sniffer se retry sau 5 giay...")
                        time.sleep(5)
                        continue
                        
                    try:
                        print("[+] Ket noi Chrome Debug thanh cong!")
                        self.context.playwright_connected = True
                        
                        page = None
                        while self.context.running and not page:
                            pages = context.pages
                            for p_curr in pages:
                                if p_curr.url and is_socialpeta_url(p_curr.url):
                                    page = p_curr
                                    break
                            if not page:
                                print("[*] Chua tim thay tab SocialPeta tren Chrome. Dang cho va retry sau 5 giay...")
                                time.sleep(5)
                                
                        if not self.context.running or page is None:
                            break
                            
                        print(f"[+] Da nhan dien tab SocialPeta dang hoat dong: {page.url}")
                        self.context.active_page = page
                        
                        def handle_response(response):
                            url = response.url
                            if response.status in (403, 429, 500):
                                if "/creative/" in url or "/creative-rank/" in url:
                                    print(f"[-] API error returned ({response.status}) on: {url}")
                                return
                                
                            if "/creative/list" in url or "/creative-rank/list" in url:
                                try:
                                    body = response.json()
                                    self._process_api_response(body)
                                except Exception as ex:
                                    print(f"[-] Sniffer error: {ex}")
                                    
                        page.on("response", handle_response)
                        
                        if self.context.total_pages:
                            try:
                                self.run_pagination_loop(page)
                            except Exception as e:
                                print(f"[-] Loi trong qua trinh dieu huong pagination: {e}")
                            self.context.total_pages = None
                        
                        while self.context.running:
                            if page.is_closed():
                                print("\n[-] CANH BAO: Tab SocialPeta da bi dong.")
                                self.context.active_page = None
                                break
                                
                            self.context.youtube_service._youtube_extract_worker()
                            
                            url = page.url
                            if "login" in url:
                                print("\n[-] CANH BAO: Trang SocialPeta bi dang xuat / session het han.")
                                self.context.pause_event.clear()
                                print("[*] Da tam dung luong tai video. Vui long dang nhap lai tren trinh duyet.")
                                
                                while self.context.running and "login" in page.url:
                                    time.sleep(2)
                                if self.context.running:
                                    self.context.pause_event.set()
                                    print("[+] Da phat hien dang nhap lai. Tiep tuc luong tai video.")
                                    
                            time.sleep(0.5)
                    finally:
                        if browser:
                            browser.close()
            except Exception as e:
                print(f"[-] Stream 1 Sniffer crashed: {e}. Dang khoi dong lai sau 5 giay...")
                self.context.active_page = None
                time.sleep(5)

    def run_pagination_loop(self, page):
        if not self.context:
            return
            
        N = self.context.total_pages
        if not N or N <= 0:
            return
            
        print(f"[*] Bat dau tu dong hoa pagination cho {N} trang...")
        
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        except Exception:
            pass
            
        active_page_num = 1
        try:
            active_item = page.locator("li.ant-pagination-item-active").first
            if active_item.is_visible():
                txt = active_item.text_content().strip()
                if txt.isdigit():
                    active_page_num = int(txt)
        except Exception:
            pass
            
        print(f"[*] Trang hien tai tren browser: {active_page_num}")
        
        self.context.pagination_target_pages = N
        if N == 1:
            if active_page_num == 1:
                click_sequence = [2, 1]
            else:
                click_sequence = [1]
        else:
            if active_page_num == 1:
                click_sequence = list(range(2, N + 1)) + [1]
            else:
                click_sequence = list(range(1, N + 1))
        
        transition_successful = False
        for page_num in click_sequence:
            if not self.context.running:
                break
                
            is_helper_page = (page_num > N)
            if is_helper_page:
                print(f"[*] Dang chuyen den helper page Trang {page_num}...")
            else:
                print(f"[*] Dang chuyen den Trang {page_num}...")
            self.context.current_page = page_num
            
            self.context.page_packet_received.clear()
            self.context.last_packet_empty = False
            
            success = False
            
            # Special case: target is page 1, browser is on page 1, and transition failed/unavailable.
            if page_num == 1 and active_page_num == 1 and not transition_successful:
                print(f"[*] Su dung soft trigger de tai lai Trang 1 vi transition that bai hoac khong kha dung.")
                if self.soft_trigger(page):
                    success = True
            else:
                for retry in range(1, 4):
                    if not self.context.running:
                        break
                        
                    nav_ok = False
                    if page_num <= 5:
                        nav_ok = self.context.utils_service._click_page_button(page, page_num)
                    else:
                        nav_ok = self.context.utils_service._jump_to_page(page, page_num)
                        
                    if not nav_ok:
                        if is_helper_page:
                            print(f"[*] Helper transition page {page_num} khong ton tai. Bo qua transition.")
                            break
                        print(f"[-] Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Dang scroll va thu lai...")
                        try:
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1.5)
                        except Exception:
                            pass
                        continue
                    
                    timeout_val = 10.0 if is_helper_page else 15.0
                    received = self.context.page_packet_received.wait(timeout=timeout_val)
                    if received:
                        success = True
                        if is_helper_page:
                            transition_successful = True
                            print(f"[+] Da chuyen thanh cong den helper page Trang {page_num}.")
                        else:
                            print(f"[+] Da nhan phan hoi API cho Trang {page_num}.")
                        break
                    else:
                        if is_helper_page:
                            success = True
                            transition_successful = True
                            print(f"[!] CANH BAO: Helper page {page_num} packet timeout, nhung van tiep tuc...")
                            break
                        print(f"[-] Retry {retry}/3: Timeout cho doi goi tin Trang {page_num}.")
                        
            if not success:
                if is_helper_page:
                    print(f"[*] Chuyen den helper page that bai, tiep tuc sequence.")
                    continue
                print(f"[!] CANH BAO: That bai khi chuyen den Trang {page_num} sau 3 lan thu.")
                continue
                
            if is_helper_page:
                time.sleep(1.5)
                continue
                
            if self.context.last_packet_empty:
                print(f"[*] Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            time.sleep(2)
            
        print("[+] Hoan thanh quynh trinh Pagination Sniffing.")

    def soft_trigger(self, page) -> bool:
        if not self.context:
            return False
            
        if not page or page.is_closed():
            print(f"[-] Page khong hop le hoac da dong.")
            return False
            
        print(f"[*] Dang kich hoat Soft Trigger...")
        self.context.page_packet_received.clear()
            
        for attempt in range(1, 4):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.0)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1.0)
                
                if self.context.page_packet_received.is_set():
                    print(f"[+] Soft Trigger thanh cong o lan thu {attempt}!")
                    return True
                    
                search_selectors = [
                    "button.ant-btn-primary:has-text('Search')",
                    "button.el-button--primary:has-text('Tìm kiếm')",
                    "button:has-text('Search')",
                    "button:has-text('Tìm kiếm')",
                    ".search-btn",
                    ".search-button"
                ]
                for sel in search_selectors:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible() and loc.is_enabled():
                            loc.click()
                            time.sleep(2.0)
                            break
                    except Exception:
                        pass
                        
                if self.context.page_packet_received.is_set():
                    print(f"[+] Soft Trigger thanh cong o lan thu {attempt}!")
                    return True
            except Exception as e:
                import traceback
                print(f"[-] Soft Trigger attempt {attempt} failed: {e}\n{traceback.format_exc()}")
                
        print(f"[!] CANH BAO: Soft Trigger that bai sau 3 lan thu.")
        return False
