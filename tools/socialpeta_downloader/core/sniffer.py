# tools/socialpeta_downloader/core/sniffer.py
"""
Responsibility: Sniffs network packets, parses creative items, and manages tab pagination flow.
"""

import os
import re
import time
import queue
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from socialpeta_downloader.core.protocols import IEngineContext

class SnifferService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def _recursive_find_creatives(self, obj) -> List[dict]:
        if self.context and self.context.utils_service:
            return self.context.utils_service._recursive_find_creatives(obj)
        return []

    def _parse_creative_item(self, raw_item: dict) -> dict:
        if self.context and self.context.utils_service:
            return self.context.utils_service._parse_creative_item(raw_item)
        return {}


    def _process_api_response_for_tab(self, tab_index: int, data: dict):
        if not self.context:
            return
            
        try:
            items = self._recursive_find_creatives(data)
            if not items:
                self.context.tab_last_packet_empty[tab_index] = True
                print(f"[*] Tab {tab_index} Sniffer: Nhan goi tin nhung danh sach trong.")
            else:
                self.context.tab_last_packet_empty[tab_index] = False
                
            new_count = 0
            tab_dir = os.path.join(self.context.temp_queue_dir, f"tab{tab_index}")
            os.makedirs(tab_dir, exist_ok=True)
            
            for raw_item in items:
                parsed = self._parse_creative_item(raw_item)
                if not parsed["ad_id"]:
                    continue
                    
                fpath = os.path.join(tab_dir, f"{parsed['ad_id']}.json")
                parsed["fpath"] = fpath
                parsed["subfolder"] = self.context.tab_states[tab_index].get("subfolder", "")
                parsed["subfolder_path"] = self.context.tab_states[tab_index].get("subfolder_path", "")
                
                with self.context.history_lock:
                    if self.context.utils_service._is_ad_already_downloaded(parsed["ad_id"]):
                        continue
                    if self.context.utils_service._is_ad_already_downloading_or_done(parsed["ad_id"]):
                        continue
                
                download_mode = getattr(self.context, "download_mode", "all")
                if download_mode == "image":
                    if parsed["media_type"] not in ("image", "youtube_thumbnail"):
                        continue
                elif download_mode == "youtube":
                    if parsed["media_type"] not in ("youtube_video", "youtube_click_required"):
                        continue
                
                if parsed["media_type"] == "youtube_click_required":
                    self.context.utils_service._save_item_state(parsed)
                    self.context.tab_youtube_queues[tab_index].put(parsed)
                else:
                    self.context.utils_service._save_item_state(parsed)
                    new_count += 1
                    self.context.pending_downloads.put((time.time(), parsed["fpath"]))
                    
            if new_count > 0:
                self.context.tab_states[tab_index]["scraped_count"] += new_count
                print(f"[+] Tab {tab_index}: Phat hien va xep hang {new_count} media moi.")
                
            self.context.tab_packet_received_events[tab_index].set()
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Tab {tab_index} Sniffer error parsing creative list: {e}\n{traceback.format_exc()}")
            else:
                print(f"[-] Tab {tab_index} Sniffer error parsing creative list: {e}\n{traceback.format_exc()}")
            self.context.tab_packet_received_events[tab_index].set()

    def run_tab_pagination_loop(self, tab_index: int, page, total_pages: int):
        if not self.context:
            return
            
        N = total_pages
        if not N or N <= 0:
            return
            
        print(f"[*] Tab {tab_index}: Bat dau pagination tu dong cho {N} trang...")
        
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
            close_btn = page.locator("button.ant-modal-close, .ant-modal-close, button:has(span.ant-modal-close-x), .anticon-close").first
            if close_btn.is_visible():
                close_btn.click(timeout=1000)
                time.sleep(0.5)
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
            
        print(f"[*] Tab {tab_index} - Trang hien tai: {active_page_num}")
        
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
            if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                break
                
            if page.is_closed():
                print(f"[-] Tab {tab_index}: Page is closed. Exiting pagination loop.")
                self.context.tab_states[tab_index]["status"] = "closed"
                break
                
            try:
                page.keyboard.press("Escape")
                time.sleep(0.5)
                close_btn = page.locator("button.ant-modal-close, .ant-modal-close, button:has(span.ant-modal-close-x), .anticon-close").first
                if close_btn.is_visible():
                    close_btn.click(timeout=1000)
                    time.sleep(0.5)
            except Exception:
                pass
                
            print(f"[*] Tab {tab_index}: Dang chuyen den Trang {page_num}...")
            self.context.tab_states[tab_index]["current_page"] = page_num
            
            self.context.tab_packet_received_events[tab_index].clear()
            self.context.tab_last_packet_empty[tab_index] = False
            
            success = False
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.8)
            except Exception:
                pass
                
            for retry in range(1, 4):
                if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                    break
                    
                nav_ok = False
                if page_num <= 5:
                    nav_ok = self.context.utils_service._click_page_button(page, page_num)
                else:
                    nav_ok = self.context.utils_service._jump_to_page(page, page_num)
                    
                if not nav_ok:
                    print(f"[-] Tab {tab_index} Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Scroll va thu lai...")
                    try:
                        page.keyboard.press("Escape")
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1.5)
                    except Exception:
                        pass
                    continue
                
                received = self.context.tab_packet_received_events[tab_index].wait(timeout=30.0)
                if received:
                    success = True
                    print(f"[+] Tab {tab_index}: Da nhan phan hoi API cho Trang {page_num}.")
                    break
                else:
                    print(f"[-] Tab {tab_index} Retry {retry}/3: Timeout cho doi goi tin Trang {page_num}.")
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                            
            if not success:
                print(f"[!] Tab {tab_index} CANH BAO: That bai khi chuyen den Trang {page_num} sau 3 lan thu.")
                continue
                
            if self.context.tab_last_packet_empty.get(tab_index, False):
                print(f"[*] Tab {tab_index}: Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            print(f"[*] Tab {tab_index}: Dang scroll de load anh cho tat ca card tren Trang {page_num}...")
            try:
                for i in range(1, 13):
                    if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                        break
                    page.evaluate(f"window.scrollTo(0, {i * 1000})")
                    time.sleep(0.25)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.8)
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Tab {tab_index} Scroll error: {e}\n{traceback.format_exc()}")
                else:
                    print(f"[-] Tab {tab_index} Scroll error: {e}\n{traceback.format_exc()}")
                
            q = self.context.tab_youtube_queues.get(tab_index)
            if q and not q.empty():
                print(f"[*] Tab {tab_index}: Phat hien {q.qsize()} quang cao YouTube can click trich xuat inline...")
                while not q.empty():
                    if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                        break
                    self.context.youtube_service._youtube_extract_worker_for_tab(tab_index, page)
 
            time.sleep(2)
            
        print(f"[+] Tab {tab_index}: Hoan thanh quy trinh Pagination Sniffing.")

    def soft_trigger(self, tab_index: int) -> bool:
        if not self.context:
            return False
            
        page = self.context.active_pages.get(tab_index)
        if not page or page.is_closed():
            print(f"[-] Tab {tab_index} khong hop le hoac da dong.")
            return False
            
        print(f"[*] Dang kich hoat Soft Trigger tren Tab {tab_index}...")
        if tab_index in self.context.tab_packet_received_events:
            self.context.tab_packet_received_events[tab_index].clear()
            
        for attempt in range(1, 4):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.0)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1.0)
                
                if tab_index in self.context.tab_packet_received_events and self.context.tab_packet_received_events[tab_index].is_set():
                    print(f"[+] Soft Trigger Tab {tab_index} thanh cong o lan thu {attempt}!")
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
                        
                if tab_index in self.context.tab_packet_received_events and self.context.tab_packet_received_events[tab_index].is_set():
                    print(f"[+] Soft Trigger Tab {tab_index} thanh cong o lan thu {attempt}!")
                    return True
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Soft Trigger attempt {attempt} failed: {e}\n{traceback.format_exc()}")
                else:
                    print(f"[-] Soft Trigger attempt {attempt} failed: {e}\n{traceback.format_exc()}")
                
        print(f"[!] CANH BAO: Soft Trigger Tab {tab_index} that bai sau 3 lan thu.")
        return False
