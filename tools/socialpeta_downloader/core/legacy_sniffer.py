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
        
        for page_num in click_sequence:
            if not self.context.running:
                break
                
            print(f"[*] Dang chuyen den Trang {page_num}...")
            
            self.context.page_packet_received.clear()
            self.context.last_packet_empty = False
            
            success = False
            for retry in range(1, 4):
                if not self.context.running:
                    break
                    
                nav_ok = False
                if page_num <= 5:
                    nav_ok = self.context.utils_service._click_page_button(page, page_num)
                else:
                    nav_ok = self.context.utils_service._jump_to_page(page, page_num)
                    
                if not nav_ok:
                    print(f"[-] Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Dang scroll va thu lai...")
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1.5)
                    except Exception:
                        pass
                    continue
                
                received = self.context.page_packet_received.wait(timeout=15.0)
                if received:
                    success = True
                    print(f"[+] Da nhan phan hoi API cho Trang {page_num}.")
                    break
                else:
                    print(f"[-] Retry {retry}/3: Timeout cho doi goi tin Trang {page_num}.")
                    
            if not success:
                print(f"[!] CANH BAO: That bai khi chuyen den Trang {page_num} sau 3 lan thu.")
                continue
                
            if self.context.last_packet_empty:
                print(f"[*] Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            time.sleep(2)
            
        print("[+] Hoan thanh quynh trinh Pagination Sniffing.")
