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
from typing import TYPE_CHECKING, Any, Optional, Dict

class SnifferMixin:
    temp_queue_dir: str
    history_lock: threading.RLock
    tab_youtube_queues: Dict[int, queue.Queue]
    pending_downloads: queue.PriorityQueue
    tab_states: Dict[int, Dict[str, Any]]
    stats_lock: threading.Lock
    stats: Dict[str, int]
    tab_packet_received_events: Dict[int, threading.Event]
    running: bool
    tab_running_events: Dict[int, threading.Event]
    active_pages: Dict[int, Any]
    tab_last_packet_empty: Dict[int, bool]

    if TYPE_CHECKING:
        # Resolve type checker warnings without defining them at runtime
        def _is_ad_already_downloaded(self, ad_id: str) -> bool: ...
        def _is_ad_already_downloading_or_done(self, ad_id: str, exclude_path: Optional[str] = None) -> bool: ...
        def _save_item_state(self, item: dict) -> None: ...
        def _click_page_button(self, page: Any, page_num: int) -> bool: ...
        def _jump_to_page(self, page: Any, page_num: int) -> bool: ...
        def _youtube_extract_worker_for_tab(self, tab_index: int, page: Any) -> None: ...

    def _recursive_find_creatives(self, obj) -> list[dict]:
        if isinstance(obj, dict):
            has_id = ('id' in obj or 'creative_id' in obj or 'creativeId' in obj or 
                      'creativeIdStr' in obj or 'ad_key' in obj)
            has_media = ('video_url' in obj or 'videoUrl' in obj or 'media_url' in obj or 'mediaUrl' in obj or 
                         'video' in obj or 'url' in obj or 'image_url' in obj or 'imageUrl' in obj or 
                         'image' in obj or 'thumbnail' in obj or 'cover' in obj or 'video_cover' in obj or
                         'resource_urls' in obj or 'preview_img_url' in obj)
            has_app = ('app_name' in obj or 'appName' in obj or 'app_title' in obj or 
                       'title' in obj or 'advertiser_name' in obj)
            
            if has_id and (has_media or has_app):
                return [obj]
                
            items = []
            for v in obj.values():
                items.extend(self._recursive_find_creatives(v))
            return items
        elif isinstance(obj, list):
            items = []
            for item in obj:
                items.extend(self._recursive_find_creatives(item))
            return items
        return []

    def _parse_creative_item(self, raw_item: dict) -> dict:
        ad_id = str(raw_item.get('id') or raw_item.get('creative_id') or raw_item.get('creativeId') or raw_item.get('creativeIdStr') or raw_item.get('ad_key') or '')
        
        video_url = raw_item.get('video_url') or raw_item.get('videoUrl') or raw_item.get('media_url') or raw_item.get('mediaUrl') or raw_item.get('video') or ''
        image_url = raw_item.get('image_url') or raw_item.get('imageUrl') or raw_item.get('image') or raw_item.get('thumbnail') or raw_item.get('cover') or raw_item.get('video_cover') or raw_item.get('preview_img_url') or ''
        
        resource_urls = raw_item.get('resource_urls') or []
        if isinstance(resource_urls, list):
            for res in resource_urls:
                if isinstance(res, dict):
                    if not video_url:
                        video_url = res.get('video_url') or res.get('videoUrl') or ''
                    if not image_url:
                        image_url = res.get('image_url') or res.get('imageUrl') or ''
                        
        if isinstance(video_url, list) and video_url:
            video_url = video_url[0]
        elif isinstance(video_url, dict):
            video_url = video_url.get('url') or ''
        video_url = str(video_url).strip()
        
        youtube_url = raw_item.get('youtube_url') or raw_item.get('youtubeUrl') or ''
        if isinstance(youtube_url, list) and youtube_url:
            youtube_url = youtube_url[0]
        youtube_url = str(youtube_url).strip()
        
        if isinstance(image_url, list) and image_url:
            image_url = image_url[0]
        elif isinstance(image_url, dict):
            image_url = image_url.get('url') or ''
        image_url = str(image_url).strip()
        
        duration_val = raw_item.get('duration') or raw_item.get('duration_sec') or raw_item.get('video_duration')
        if duration_val is not None:
            try:
                duration = int(float(duration_val))
            except ValueError:
                duration = None
        else:
            duration = None
            
        impression = raw_item.get('impression') or raw_item.get('show_num') or raw_item.get('exposure') or raw_item.get('all_exposure_value') or ''
        heat = raw_item.get('heat') or raw_item.get('hot') or ''
        platform = str(raw_item.get('platform') or raw_item.get('system') or raw_item.get('os') or 'unknown').strip().lower()
        area = raw_item.get('area') or raw_item.get('country') or raw_item.get('region') or 'unknown'
        if isinstance(area, list) and area:
            area = area[0]

        pub_candidates = [raw_item.get('publisher'), raw_item.get('channel'), raw_item.get('source'), platform]
        publisher = ""
        for cand in pub_candidates:
            if cand and str(cand).strip().lower() not in ("", "none", "null", "undefined"):
                publisher = str(cand).strip()
                break

        app_name = raw_item.get('app_name') or raw_item.get('appName') or raw_item.get('app_title') or raw_item.get('advertiser_name') or raw_item.get('title') or 'UnknownApp'
            
        copywriting_language = raw_item.get('copywriting_language') or raw_item.get('language') or raw_item.get('lang') or ''
        title = raw_item.get('title') or raw_item.get('ad_title') or ''
        body = raw_item.get('body') or raw_item.get('desc') or raw_item.get('description') or raw_item.get('content') or raw_item.get('copywriting') or ''
        deployment_time = raw_item.get('deployment_time') or raw_item.get('first_show_time') or raw_item.get('firstShowTime') or raw_item.get('online_time') or ''
        
        media_type = "video"
        is_youtube = (platform == "youtube" or
                      "youtube" in video_url.lower() or "youtu.be" in video_url.lower() or 
                      "youtube" in youtube_url.lower() or "youtu.be" in youtube_url.lower() or
                      (not video_url and not youtube_url and "youtube" in publisher.lower()))
                      
        if is_youtube:
            print(f"[YouTube] ad_key={ad_id} platform={platform}")

        if not video_url and image_url and not is_youtube:
            media_type = "image"
        elif is_youtube:
            is_real_youtube_link = (
                (youtube_url and ("youtube" in youtube_url.lower() or "youtu.be" in youtube_url.lower())) or
                (video_url and ("youtube" in video_url.lower() or "youtu.be" in video_url.lower()))
            )
            if is_real_youtube_link:
                if duration is not None and duration > 0:
                    media_type = "youtube_video"
                else:
                    media_type = "youtube_thumbnail"
            elif not youtube_url and video_url and not ("youtube" in video_url.lower() or "youtu.be" in video_url.lower()):
                media_type = "video"
            else:
                media_type = "youtube_click_required"
        else:
            media_type = "video"
            
        return {
            "ad_id": ad_id,
            "video_name": "",
            "media_type": media_type,
            "video_url": video_url,
            "youtube_url": youtube_url,
            "image_url": image_url,
            "duration": duration if duration is not None else "",
            "impression": str(impression).strip(),
            "heat": str(heat).strip(),
            "platform": platform,
            "download_time": "",
            "publisher": str(publisher).strip(),
            "app_name": str(app_name).strip(),
            "area": str(area).strip().upper(),
            "copywriting_language": str(copywriting_language).strip(),
            "title": str(title).strip(),
            "body": str(body).strip(),
            "deployment_time": str(deployment_time).strip(),
            "saved_path": "",
            "file_size": 0,
            "status": "pending"
        }

    def _process_api_response_for_tab(self, tab_index: int, data: dict):
        try:
            items = self._recursive_find_creatives(data)
            if not items:
                self.tab_last_packet_empty[tab_index] = True
                print(f"[*] Tab {tab_index} Sniffer: Nhan goi tin nhung danh sach trong.")
            else:
                self.tab_last_packet_empty[tab_index] = False
                
            new_count = 0
            tab_dir = os.path.join(self.temp_queue_dir, f"tab{tab_index}")
            os.makedirs(tab_dir, exist_ok=True)
            
            for raw_item in items:
                parsed = self._parse_creative_item(raw_item)
                if not parsed["ad_id"]:
                    continue
                    
                fpath = os.path.join(tab_dir, f"{parsed['ad_id']}.json")
                parsed["fpath"] = fpath
                parsed["subfolder"] = self.tab_states[tab_index].get("subfolder", "")
                parsed["subfolder_path"] = self.tab_states[tab_index].get("subfolder_path", "")
                
                with self.history_lock:
                    if self._is_ad_already_downloaded(parsed["ad_id"]):
                        continue
                    if self._is_ad_already_downloading_or_done(parsed["ad_id"]):
                        continue
                
                if parsed["media_type"] == "youtube_click_required":
                    self.tab_youtube_queues[tab_index].put(parsed)
                else:
                    self._save_item_state(parsed)
                    new_count += 1
                    self.pending_downloads.put((time.time(), parsed["fpath"]))
                    
            if new_count > 0:
                self.tab_states[tab_index]["scraped_count"] += new_count
                with self.stats_lock:
                    self.stats["total_sniffed"] += new_count
                print(f"[+] Tab {tab_index}: Phat hien va xep hang {new_count} media moi.")
                
            self.tab_packet_received_events[tab_index].set()
        except Exception as e:
            print(f"[-] Tab {tab_index} Sniffer error parsing creative list: {e}")
            self.tab_packet_received_events[tab_index].set()

    def run_tab_pagination_loop(self, tab_index: int, page, total_pages: int):
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
        
        click_sequence = list(range(1, N + 1))
        
        for page_num in click_sequence:
            if not self.running or not self.tab_running_events[tab_index].is_set():
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
            self.tab_states[tab_index]["current_page"] = page_num
            
            self.tab_packet_received_events[tab_index].clear()
            self.tab_last_packet_empty[tab_index] = False
            
            success = False
            if page_num == 1 and active_page_num == 1:
                print(f"[*] Tab {tab_index}: Dang dung soft trigger de sniff goi tin Trang 1...")
                success = self.soft_trigger(tab_index)
            else:
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(0.8)
                except Exception:
                    pass
                    
                for retry in range(1, 4):
                    if not self.running or not self.tab_running_events[tab_index].is_set():
                        break
                        
                    nav_ok = False
                    if page_num <= 5:
                        nav_ok = self._click_page_button(page, page_num)
                    else:
                        nav_ok = self._jump_to_page(page, page_num)
                        
                    if not nav_ok:
                        print(f"[-] Tab {tab_index} Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Scroll va thu lai...")
                        try:
                            page.keyboard.press("Escape")
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1.5)
                        except Exception:
                            pass
                        continue
                    
                    received = self.tab_packet_received_events[tab_index].wait(timeout=30.0)
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
                
            if self.tab_last_packet_empty.get(tab_index, False):
                print(f"[*] Tab {tab_index}: Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            print(f"[*] Tab {tab_index}: Dang scroll de load anh cho tat ca card tren Trang {page_num}...")
            try:
                for i in range(1, 13):
                    if not self.running or not self.tab_running_events[tab_index].is_set():
                        break
                    page.evaluate(f"window.scrollTo(0, {i * 1000})")
                    time.sleep(0.25)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.8)
            except Exception as e:
                print(f"[-] Tab {tab_index} Scroll error: {e}")
                
            q = self.tab_youtube_queues.get(tab_index)
            if q and not q.empty():
                print(f"[*] Tab {tab_index}: Phat hien {q.qsize()} quang cao YouTube can click trich xuat inline...")
                while not q.empty():
                    if not self.running or not self.tab_running_events[tab_index].is_set():
                        break
                    self._youtube_extract_worker_for_tab(tab_index, page)
 
            time.sleep(2)
            
        print(f"[+] Tab {tab_index}: Hoan thanh quy trinh Pagination Sniffing.")

    def soft_trigger(self, tab_index: int) -> bool:
        page = self.active_pages.get(tab_index)
        if not page or page.is_closed():
            print(f"[-] Tab {tab_index} khong hop le hoac da dong.")
            return False
            
        print(f"[*] Dang kich hoat Soft Trigger tren Tab {tab_index}...")
        if tab_index in self.tab_packet_received_events:
            self.tab_packet_received_events[tab_index].clear()
            
        for attempt in range(1, 4):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.0)
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1.0)
                
                if tab_index in self.tab_packet_received_events and self.tab_packet_received_events[tab_index].is_set():
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
                        
                if tab_index in self.tab_packet_received_events and self.tab_packet_received_events[tab_index].is_set():
                    print(f"[+] Soft Trigger Tab {tab_index} thanh cong o lan thu {attempt}!")
                    return True
            except Exception as e:
                print(f"[-] Soft Trigger attempt {attempt} failed: {e}")
                
        print(f"[!] CANH BAO: Soft Trigger Tab {tab_index} that bai sau 3 lan thu.")
        return False
