# tools/socialpeta_downloader/core/sniffer.py
"""
Responsibility: Sniffs network packets, parses creative items, and manages tab pagination flow.
"""

import os
import re
import time
import json
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
            
        N = self.context.tab_states[tab_index].get("target_pages", 0)
        current_page = self.context.tab_states[tab_index].get("current_page", 1)
        if N > 0 and current_page > N:
            self.context.tab_packet_received_events[tab_index].set()
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
                elif parsed["media_type"] in ("image", "youtube_thumbnail"):
                    self.context.utils_service._save_item_state(parsed)
                    new_count += 1
                    self.context.pending_downloads.put((time.time(), parsed["fpath"]))
                else: # parsed["media_type"] == "video"
                    # Defer video CDN downloads: save state but do NOT queue yet
                    self.context.utils_service._save_item_state(parsed)
                    
            if new_count > 0:
                self.context.tab_states[tab_index]["scraped_count"] += new_count
                print(f"[+] Tab {tab_index}: Phat hien va xep hang {new_count} media (anh) moi.")
                
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
        
        transition_successful = False
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
                
            is_helper_page = (page_num > N)
            if is_helper_page:
                print(f"[*] Tab {tab_index}: Dang chuyen den helper page Trang {page_num}...")
            else:
                print(f"[*] Tab {tab_index}: Dang chuyen den Trang {page_num}...")
            self.context.tab_states[tab_index]["current_page"] = page_num
            
            self.context.tab_packet_received_events[tab_index].clear()
            self.context.tab_last_packet_empty[tab_index] = False
            
            success = False
            
            # Special case: target is page 1, browser is on page 1, and transition failed/unavailable.
            if page_num == 1 and active_page_num == 1 and not transition_successful:
                print(f"[*] Tab {tab_index}: Su dung soft trigger de tai lai Trang 1 vi transition that bai hoac khong kha dung.")
                if self.soft_trigger(tab_index):
                    success = True
            else:
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
                        if is_helper_page:
                            print(f"[*] Tab {tab_index}: Helper transition page {page_num} khong ton tai. Bo qua transition.")
                            break
                        print(f"[-] Tab {tab_index} Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Scroll va thu lai...")
                        try:
                            page.keyboard.press("Escape")
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1.5)
                        except Exception:
                            pass
                        continue
                    
                    timeout_val = 10.0 if is_helper_page else 30.0
                    received = self.context.tab_packet_received_events[tab_index].wait(timeout=timeout_val)
                    if received:
                        success = True
                        if is_helper_page:
                            transition_successful = True
                            print(f"[+] Tab {tab_index}: Da chuyen thanh cong den helper page Trang {page_num}.")
                        else:
                            print(f"[+] Tab {tab_index}: Da nhan phan hoi API cho Trang {page_num}.")
                        break
                    else:
                        if is_helper_page:
                            success = True
                            transition_successful = True
                            print(f"[!] Tab {tab_index} CANH BAO: Helper page {page_num} packet timeout, nhung van tiep tuc...")
                            break
                        print(f"[-] Tab {tab_index} Retry {retry}/3: Timeout cho doi goi tin Trang {page_num}.")
                        try:
                            page.keyboard.press("Escape")
                        except Exception:
                            pass
                                
            if not success:
                if is_helper_page:
                    print(f"[*] Tab {tab_index}: Chuyen den helper page that bai, tiep tuc sequence.")
                    continue
                print(f"[!] Tab {tab_index} CANH BAO: That bai khi chuyen den Trang {page_num} sau 3 lan thu.")
                continue
                
            if is_helper_page:
                time.sleep(1.5)
                continue
                
            if self.context.tab_last_packet_empty.get(tab_index, False):
                print(f"[*] Tab {tab_index}: Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            # Wait 1.0 second for the DOM elements to start rendering
            time.sleep(1.0)
            
            # 1. Scroll page first to render cards and load lazy-loaded image/video CDN resources
            print(f"[*] Tab {tab_index}: Dang scroll de render cards va load anh tren Trang {page_num}...")
            try:
                for i in range(1, 13):
                    if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                        break
                    page.evaluate(f"window.scrollTo(0, {i * 1000})")
                    time.sleep(0.2)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.5)
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Tab {tab_index} Scroll error: {e}\n{traceback.format_exc()}")
                else:
                    print(f"[-] Tab {tab_index} Scroll error: {e}\n{traceback.format_exc()}")

            # 2. Upgrade youtube items using DOM icon
            self._upgrade_youtube_items_via_dom(tab_index, page)
            
            # 3. Extract YouTube items before anything else
            q = self.context.tab_youtube_queues.get(tab_index)
            if q and not q.empty():
                print(f"[*] Tab {tab_index}: Phat hien {q.qsize()} quang cao YouTube can click trich xuat inline...")
                while not q.empty():
                    if not self.context.running or not self.context.tab_running_events[tab_index].is_set():
                        break
                    self.context.youtube_service._youtube_extract_worker_for_tab(tab_index, page)

            # 4. Queue deferred video CDN items into pending_downloads
            new_cdn_videos_count = 0
            db_path = self.context.utils_service.get_db_path()
            if os.path.exists(db_path):
                import sqlite3
                conn = sqlite3.connect(db_path, timeout=10.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT ad_id, fpath, item_json FROM ad_metadata WHERE status = 'pending'")
                    for ad_id, fpath, item_json in cursor.fetchall():
                        try:
                            norm_fpath = os.path.normpath(fpath)
                            parts = norm_fpath.replace("\\", "/").split("/")
                            if f"tab{tab_index}" in parts:
                                item = json.loads(item_json)
                                if item.get("media_type") == "video":
                                    self.context.pending_downloads.put((time.time(), fpath))
                                    new_cdn_videos_count += 1
                        except Exception as inner_ex:
                            print(f"[-] Tab {tab_index}: Loi phan tich item tu SQLite: {inner_ex}")
                except Exception as ex:
                    print(f"[-] Tab {tab_index}: Loi truy van video pending tu SQLite: {ex}")
                finally:
                    conn.close()
            
            if new_cdn_videos_count > 0:
                self.context.tab_states[tab_index]["scraped_count"] += new_cdn_videos_count
                print(f"[+] Tab {tab_index}: Da day {new_cdn_videos_count} video CDN thuc su vao hang doi tai.")
 
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

    def _upgrade_youtube_items_via_dom(self, tab_index: int, page):
        if not self.context:
            return
            
        print(f"[*] Tab {tab_index}: Dang quet giao dien de phat hien va nang cap cac item YouTube bi sot...")
        try:
            # 1. Quet giao dien lay cac card chua icon youtube
            youtube_cards = page.evaluate("""() => {
                const getHash = (url) => {
                    if (!url) return null;
                    const m = url.match(/([a-fA-F0-9]{32})/);
                    if (m) return m[1];
                    const parts = url.split('?')[0].split('/');
                    const file = parts[parts.length - 1];
                    const dotIdx = file.lastIndexOf('.');
                    return dotIdx !== -1 ? file.substring(0, dotIdx) : file;
                };
                
                const cards = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light, [class*="creative-card"]'));
                const results = [];
                for (const c of cards) {
                    const hasYoutubeIcon = !!c.querySelector('.net-icon-youtube') || 
                                           !!c.querySelector('[class*="net-icon-youtube"]') ||
                                           !!c.querySelector('[class*="-youtube"]');
                    if (hasYoutubeIcon) {
                        const hashes = [];
                        c.querySelectorAll('img').forEach(img => {
                            const urls = [
                                img.src,
                                img.getAttribute('src'),
                                img.getAttribute('data-src'),
                                img.getAttribute('data-original'),
                                img.getAttribute('lazy-src'),
                                img.getAttribute('data-lazy-src')
                            ];
                            urls.forEach(url => {
                                const h = getHash(url);
                                if (h) hashes.push(h);
                            });
                        });
                        c.querySelectorAll('video').forEach(vid => {
                            const urls = [
                                vid.src,
                                vid.getAttribute('src'),
                                vid.getAttribute('data-src'),
                                vid.getAttribute('poster'),
                                vid.getAttribute('data-poster')
                            ];
                            vid.querySelectorAll('source').forEach(srcEl => {
                                urls.push(srcEl.src);
                                urls.push(srcEl.getAttribute('src'));
                                urls.push(srcEl.getAttribute('data-src'));
                            });
                            urls.forEach(url => {
                                const h = getHash(url);
                                if (h) hashes.push(h);
                            });
                        });
                        results.push({
                            hashes: hashes,
                            cardText: (c.innerText || c.textContent || "").toLowerCase()
                        });
                    }
                }
                return results;
            }""")
            
            if not youtube_cards:
                print(f"[*] Tab {tab_index}: Khong tim thay card YouTube nao tren giao dien hien tai.")
                return
                
            print(f"[*] Tab {tab_index}: Tim thay {len(youtube_cards)} card co icon YouTube tren giao dien.")
            
            # 2. Truy van danh sach cac item dang la 'pending' va media_type = 'video' trong DB
            import sqlite3
            db_path = self.context.utils_service.get_db_path()
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            
            pending_videos = []
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT ad_id, fpath, item_json FROM ad_metadata WHERE status = 'pending'")
                for ad_id, fpath, item_json in cursor.fetchall():
                    try:
                        item = json.loads(item_json)
                        if item.get("media_type") == "video":
                            pending_videos.append(item)
                    except Exception:
                        pass
            except Exception as ex:
                print(f"[-] Tab {tab_index}: Loi doc ad_metadata: {ex}")
            finally:
                conn.close()
                
            if not pending_videos:
                return
                
            upgraded_count = 0
            
            # Helper to extract hash
            def get_url_hash(url):
                if not url:
                    return None
                m = re.search(r'([a-fA-F0-9]{32})', url)
                if m:
                    return m.group(1)
                parts = url.split('?')[0].split('/')
                file = parts[-1]
                dot_idx = file.rfind('.')
                return file[:dot_idx] if dot_idx != -1 else file
                
            for item in pending_videos:
                platform = item.get("platform", "").lower()
                if platform != "youtube":
                    continue
                    
                ad_id = item["ad_id"]
                img_url = item.get("image_url", "")
                vid_url = item.get("video_url", "")
                app_name = item.get("app_name", "").lower()
                title = item.get("title", "").lower()
                body = item.get("body", "").lower()
                
                img_hash = get_url_hash(img_url)
                vid_hash = get_url_hash(vid_url)
                
                matched = False
                for card in youtube_cards:
                    # Match by hash
                    if (img_hash and img_hash in card["hashes"]) or (vid_hash and vid_hash in card["hashes"]):
                        matched = True
                        break
                    # Match by text content
                    app_match = app_name and app_name != 'unknownapp' and app_name in card["cardText"]
                    title_match = title and title in card["cardText"]
                    body_match = body and body in card["cardText"]
                    if app_match and (title_match or body_match):
                        matched = True
                        break
                        
                if matched:
                    # Upgrade item to youtube_click_required
                    item["media_type"] = "youtube_click_required"
                    self.context.utils_service._save_item_state(item)
                    
                    # Them vao tab_youtube_queue
                    self.context.tab_youtube_queues[tab_index].put(item)
                    upgraded_count += 1
                    print(f"[YouTube Upgrade] Da nang cap ad_id={ad_id} tu video sang youtube_click_required vi phat hien icon YouTube.")
                    
            if upgraded_count > 0:
                print(f"[+] Tab {tab_index}: Da nang cap thanh cong {upgraded_count} item len YouTube queue.")
        except Exception as e:
            import traceback
            self.context.log("error", f"[-] Tab {tab_index} Upgrade YouTube error: {e}\n{traceback.format_exc()}")
