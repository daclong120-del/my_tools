# tools/socialpeta_downloader/core/tab_manager.py
"""
Responsibility: Multi-tab detection and management. Connects over CDP, injects tab IDs, and manages scraper threads.
"""

import os
import re
import time
import uuid
import queue
import threading
from typing import Any, Dict, List, Optional
from socialpeta_downloader.config import settings
from playwright.sync_api import sync_playwright
from socialpeta_downloader.core.utils import is_socialpeta_url
from socialpeta_downloader.core.protocols import IEngineContext

class TabScanner:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def detect_tabs(self, port: Optional[int] = None) -> list:
        """
        Connects to Chrome debug port via HTTP DevTools protocol, detects all SocialPeta tabs,
        and returns a list of active tabs. Fast, lightweight, and prevents CDP session leaks.
        """
        if not self.context:
            return []
            
        if not self.context.chrome_service.ensure_chrome_debug_port(port):
            return []
            
        port_val = port if port is not None else settings.CHROME_DEBUG_PORT
        import requests
        active_tabs = []
        try:
            resp = requests.get(f"http://127.0.0.1:{port_val}/json/list", timeout=2.0)
            if resp.status_code != 200:
                return []
            pages_list = resp.json()
            current_active_tab_ids = set()
            
            for p_info in pages_list:
                if p_info.get("type") != "page":
                    continue
                url = p_info.get("url", "")
                if not url or url == "about:blank" or not is_socialpeta_url(url):
                    continue
                    
                title = p_info.get("title") or "SocialPeta Page"
                tab_id = p_info.get("id")
                if not tab_id:
                    continue
                    
                current_active_tab_ids.add(tab_id)
                
                if tab_id not in self.context.tab_id_to_index:
                    new_idx = len(self.context.tab_id_to_index) + 1
                    self.context.tab_id_to_index[tab_id] = new_idx
                    self.context.tab_is_new[tab_id] = True
                    
                idx = self.context.tab_id_to_index[tab_id]
                
                if idx not in self.context.tab_states:
                    self.context.tab_states[idx] = {
                        "status": "new",
                        "current_page": 1,
                        "target_pages": 0,
                        "app_name": title,
                        "scraped_count": 0,
                        "url": url,
                        "title": title,
                        "tab_id": tab_id
                    }
                else:
                    self.context.tab_states[idx]["url"] = url
                    self.context.tab_states[idx]["title"] = title
                    
                active_tabs.append({
                    "index": idx,
                    "tab_id": tab_id,
                    "url": url,
                    "title": title
                })
                
            if not active_tabs:
                print("[*] No active SocialPeta tabs detected. Waiting for user to navigate manually.")
                
            all_assigned_tab_ids = list(self.context.tab_id_to_index.keys())
            for tid in all_assigned_tab_ids:
                if tid not in current_active_tab_ids:
                    idx = self.context.tab_id_to_index[tid]
                    if idx in self.context.tab_running_events:
                        self.context.tab_running_events[idx].clear()
                    if idx in self.context.tab_states:
                        self.context.tab_states[idx]["status"] = "closed"
        except requests.exceptions.Timeout:
            print(f"[-] Timeout: Chrome DevTools protocol at 127.0.0.1:{port_val} did not respond within 2.0 seconds.")
        except requests.exceptions.ConnectionError:
            print(f"[-] Connection Error: Chrome debug port {port_val} is not active or unreachable.")
        except Exception as e:
            import traceback
            print(f"[-] Error detecting tabs: {e}\n{traceback.format_exc()}")
            if self.context:
                self.context.log("error", f"[-] Error detecting tabs: {e}\n{traceback.format_exc()}")
            
        return active_tabs

    def _find_page_by_id(self, context, tab_id: str):
        if not self.context:
            return None
            
        # 1. Try matching using DevTools targetId via CDPSession
        for p in context.pages:
            try:
                if p.url and is_socialpeta_url(p.url):
                    try:
                        client = context.new_cdp_session(p)
                        target_info = client.send("Target.getTargetInfo")
                        page_target_id = target_info.get("targetInfo", {}).get("targetId")
                        if page_target_id == tab_id:
                            return p
                    except Exception as cdp_err:
                        print(f"[-] CDP session failed to get targetId: {cdp_err}")
            except Exception:
                continue
                
        # 2. Fallback: match by checking window.__tab_id
        for p in context.pages:
            try:
                if p.url and is_socialpeta_url(p.url):
                    tid = p.evaluate("window.__tab_id")
                    if tid == tab_id:
                        return p
            except Exception:
                continue
                
        # 3. Fallback: match by URL and Title
        for p in context.pages:
            try:
                if p.url and is_socialpeta_url(p.url):
                    idx = self.context.tab_id_to_index.get(tab_id)
                    if idx is not None:
                        state = self.context.tab_states.get(idx)
                        if state and p.url == state.get("url") and p.title() == state.get("title"):
                            return p
            except Exception:
                continue
                
        return None

    def _scrape_app_name_from_dom(self, page) -> Optional[str]:
        """
        Attempts to scrape the app name or advertiser name directly from the DOM of the SocialPeta page.
        """
        from urllib.parse import urlparse, parse_qs
        try:
            # 1. Try to find the app name from selected items/tags in filter bar
            tag_selectors = [
                ".ant-select-selection-item",
                ".el-select__tags-text",
                ".filter-tag",
                ".app-name",
                ".app-title",
                ".advertiser-name",
                ".game-name",
                ".advertiser-info-name",
                ".app-info-name",
                ".app-card-name"
            ]
            for sel in tag_selectors:
                try:
                    locs = page.locator(sel)
                    for i in range(locs.count()):
                        val = locs.nth(i).text_content()
                        if val:
                            val = val.strip()
                            val_lower = val.lower()
                            if val and not any(kw in val_lower for kw in [
                                "socialpeta", "guangdada", "ad search", "creative", "tải", "downloader", 
                                "tiktok", "facebook", "google", "youtube", "quảng cáo", "tìm kiếm", "all", "tất cả"
                            ]):
                                return val
                except Exception:
                    continue

            # 2. Try input values (search boxes)
            input_selectors = [
                "input[placeholder*='App' i]",
                "input[placeholder*='Package' i]",
                "input[placeholder*='Tên' i]",
                "input[placeholder*='ứng dụng' i]",
                "input[placeholder*='nhà quảng cáo' i]",
                "input[placeholder*='Search' i]",
                "input[placeholder*='Tìm' i]",
                "input.ant-input",
                "input.el-input__inner"
            ]
            for sel in input_selectors:
                try:
                    locs = page.locator(sel)
                    for i in range(locs.count()):
                        val = locs.nth(i).input_value()
                        if val:
                            val = val.strip()
                            val_lower = val.lower()
                            if val and not any(kw in val_lower for kw in [
                                "socialpeta", "guangdada", "ad search", "creative", "tải", "downloader", 
                                "tiktok", "facebook", "google", "youtube", "quảng cáo", "tìm kiếm"
                            ]):
                                return val
                except Exception:
                    continue

            # 3. Try to get any header (h1, h2, h3) that might contain the app/advertiser name
            header_selectors = ["h1", "h2", "h3"]
            for sel in header_selectors:
                try:
                    locs = page.locator(sel)
                    for i in range(locs.count()):
                        val = locs.nth(i).text_content()
                        if val:
                            val = val.strip()
                            val_lower = val.lower()
                            if val and not any(kw in val_lower for kw in [
                                "socialpeta", "guangdada", "ad search", "creative", "tải", "downloader", 
                                "tiktok", "facebook", "google", "youtube", "quảng cáo", "tìm kiếm"
                            ]):
                                return val
                except Exception:
                    continue

            # 4. Try from URL query parameters
            try:
                parsed_url = urlparse(page.url)
                qs = parse_qs(parsed_url.query)
                for param in ["appName", "app_name", "keyword", "keywords", "q"]:
                    vals = qs.get(param)
                    if vals:
                        val = vals[0].strip()
                        val_lower = val.lower()
                        if val and not any(kw in val_lower for kw in [
                            "socialpeta", "guangdada", "ad search", "creative", "tải", "downloader", 
                            "tiktok", "facebook", "google", "youtube", "quảng cáo", "tìm kiếm"
                        ]):
                            return val
            except Exception as url_err:
                print(f"[-] Error extracting app name from URL query: {url_err}")

        except Exception as e:
            import traceback
            print(f"[-] Error scraping app name from DOM: {e}\n{traceback.format_exc()}")
            if self.context:
                self.context.log("error", f"[-] Error scraping app name from DOM: {e}\n{traceback.format_exc()}")
        return None

    def run_tab_scraper(self, tab_index: int, total_pages: int, port: Optional[int] = None):
        if not self.context:
            return
            
        import queue
        import re
        from datetime import datetime

        tab_id = self.context.tab_states[tab_index]["tab_id"]
        url = self.context.tab_states[tab_index].get("url", "")
        title = self.context.tab_states[tab_index].get("title", "")
        
        # Resolve ad network
        url_lower = url.lower()
        title_lower = title.lower()
        if "tiktok" in title_lower or "tiktok" in url_lower:
            ad_network = "TikTok"
        elif "facebook" in title_lower or "facebook" in url_lower or "fb" in url_lower:
            ad_network = "Facebook"
        elif "google" in title_lower or "google" in url_lower or "gdn" in url_lower:
            ad_network = "Google"
        elif "youtube" in title_lower or "youtube" in url_lower:
            ad_network = "YouTube"
        else:
            ad_network = "SocialPeta"

        # Resolve app name
        app_name = "UnknownApp"
        if title:
            parts = re.split(r'[-|_|•]', title)
            cleaned_parts = []
            for part in parts:
                p = part.strip()
                p_lower = p.lower()
                if any(kw in p_lower for kw in [
                    "socialpeta", "guangdada", "ad search", "creative", "tải", "downloader", 
                    "tiktok", "facebook", "google", "youtube", "quảng cáo", "tìm kiếm"
                ]):
                    continue
                if p:
                    cleaned_parts.append(p)
            if cleaned_parts:
                app_name = cleaned_parts[0]
            else:
                cleaned = title
                for kw in ["SocialPeta", "Guangdada", "TikTok Ad Search", "Facebook Ad Search", "Ad Search", "Search", "TikTok", "Facebook", "Google", "YouTube"]:
                    cleaned = re.sub(re.escape(kw), "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'[\s\-_|•]+', ' ', cleaned).strip()
                if cleaned:
                    app_name = cleaned

        need_dom_fallback = not app_name or app_name == "UnknownApp"

        # Date string YYYYMMDD
        date_str = datetime.now().strftime("%Y%m%d")

        # Sanitize for safe path name
        ad_network_clean = re.sub(r'[^\w\-]', '', ad_network)
        app_name_clean = re.sub(r'[^\w\-]', '', app_name)
        
        base_name = f"{ad_network_clean}_{app_name_clean}_{date_str}"
        subfolder = base_name
        
        # Deduplication check against active tabs and existing folders
        existing_subfolders = [t.get("subfolder") for t in self.context.tab_states.values() if t.get("subfolder")]
        counter = 2
        while os.path.exists(os.path.join(self.context.download_dir, subfolder)) or subfolder in existing_subfolders:
            subfolder = f"{base_name}_{counter}"
            counter += 1

        self.context.tab_states[tab_index]["subfolder"] = subfolder
        self.context.tab_states[tab_index]["subfolder_path"] = os.path.join(self.context.download_dir, subfolder)
        if not need_dom_fallback:
            os.makedirs(self.context.tab_states[tab_index]["subfolder_path"], exist_ok=True)
            print(f"[*] Thread Scraper cho Tab {tab_index} bat dau (Pages: {total_pages})...")
            print(f"[*] Tab {tab_index} duoc gan thu muc: {self.context.tab_states[tab_index]['subfolder_path']}")
        else:
            print(f"[*] Thread Scraper cho Tab {tab_index} bat dau (Pages: {total_pages}). Dang cho lay ten app tu DOM...")
        
        self.context.tab_states[tab_index]["status"] = "running"
        self.context.tab_states[tab_index]["target_pages"] = total_pages
        self.context.tab_running_events[tab_index] = threading.Event()
        self.context.tab_running_events[tab_index].set()
        
        self.context.tab_packet_received_events[tab_index] = threading.Event()
        self.context.tab_last_packet_empty[tab_index] = False
        self.context.tab_youtube_queues[tab_index] = queue.Queue()
        
        port_val = port if port is not None else settings.CHROME_DEBUG_PORT
        browser = None
        with sync_playwright() as p:
            try:
                for attempt in range(1, 4):
                    try:
                        browser = p.chromium.connect_over_cdp(f"http://localhost:{port_val}", timeout=2000)
                        break
                    except Exception as e:
                        if attempt == 3:
                            raise e
                        print(f"[-] Tab {tab_index} CDP connect attempt {attempt} failed: {e}. Retrying in 2s...")
                        time.sleep(2.0)
                if not browser or not browser.contexts:
                    print(f"[-] Tab {tab_index}: Khong tim thay context browser.")
                    self.context.tab_states[tab_index]["status"] = "failed"
                    return
                context = browser.contexts[0]
                page = self._find_page_by_id(context, tab_id)
                if not page:
                    print(f"[-] Tab {tab_index}: Khong tim thay page voi tab_id={tab_id}")
                    self.context.tab_states[tab_index]["status"] = "closed"
                    return
                    
                self.context.active_pages[tab_index] = page
                
                # Fallback: scrape app name from DOM if regex failed to extract a valid app name
                if need_dom_fallback:
                    dom_app_name = self._scrape_app_name_from_dom(page)
                    if dom_app_name:
                        app_name = dom_app_name
                        print(f"[+] Fallback: Da lay duoc ten app tu DOM: {app_name}")
                    else:
                        self.context.utils_service.log("warning", f"Khong the trich xuat ten app tu ca title va DOM cho Tab {tab_index}. Su dung 'UnknownApp'.")
                    
                    # Re-calculate subfolder path based on the resolved app name
                    app_name_clean = re.sub(r'[^\w\-]', '', app_name)
                    base_name = f"{ad_network_clean}_{app_name_clean}_{date_str}"
                    subfolder = base_name
                    
                    # Deduplication check against active tabs and existing folders
                    existing_subfolders = [t.get("subfolder") for idx, t in self.context.tab_states.items() if idx != tab_index and t.get("subfolder")]
                    counter = 2
                    while os.path.exists(os.path.join(self.context.download_dir, subfolder)) or subfolder in existing_subfolders:
                        subfolder = f"{base_name}_{counter}"
                        counter += 1
                        
                    self.context.tab_states[tab_index]["subfolder"] = subfolder
                    self.context.tab_states[tab_index]["subfolder_path"] = os.path.join(self.context.download_dir, subfolder)
                
                # Always sync back the resolved app name to tab state
                self.context.tab_states[tab_index]["app_name"] = app_name
                
                # Make sure the directory is created
                os.makedirs(self.context.tab_states[tab_index]["subfolder_path"], exist_ok=True)
                print(f"[*] Tab {tab_index} duoc gan thu muc: {self.context.tab_states[tab_index]['subfolder_path']}")
                
                def handle_response(response):
                    url = response.url
                    if response.status in (403, 429, 500):
                        if "/creative/" in url or "/creative-rank/" in url:
                            print(f"[-] Tab {tab_index} API error returned ({response.status}) on: {url}")
                        return
                    if "/creative/list" in url or "/creative-rank/list" in url:
                        try:
                            body = response.json()
                            self.context.sniffer_service._process_api_response_for_tab(tab_index, body)
                        except Exception as ex:
                            import traceback
                            print(f"[-] Tab {tab_index} response json error: {ex}\n{traceback.format_exc()}")
                            if self.context:
                                self.context.log("error", f"[-] Tab {tab_index} response json error: {ex}\n{traceback.format_exc()}")
                            
                page.on("response", handle_response)
                
                if "login" in page.url:
                    print(f"[-] Tab {tab_index}: Yeu cau dang nhap.")
                    self.context.tab_states[tab_index]["status"] = "expired"
                    return
                    
                self.context.sniffer_service.run_tab_pagination_loop(tab_index, page, total_pages)
                
                q = self.context.tab_youtube_queues.get(tab_index)
                while self.context.running and q and not q.empty():
                    if page.is_closed():
                        break
                    self.context.youtube_service._youtube_extract_worker_for_tab(tab_index, page)
                    time.sleep(0.5)
                
                # Day not cac video CDN pending con sot (neu co) truoc khi dung scraper
                new_cdn_videos_count = 0
                db_path = self.context.utils_service.get_db_path()
                if os.path.exists(db_path):
                    import sqlite3
                    import json
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
                            except Exception:
                                pass
                    except Exception as ex:
                        print(f"[-] Tab {tab_index}: Loi truy van video pending tu SQLite: {ex}")
                    finally:
                        conn.close()
                if new_cdn_videos_count > 0:
                    self.context.tab_states[tab_index]["scraped_count"] += new_cdn_videos_count
                    print(f"[+] Tab {tab_index}: Da day not {new_cdn_videos_count} video CDN pending con lai vao hang doi tai.")
                
                self.context.tab_running_events[tab_index].clear()
                    
            except Exception as e:
                import traceback
                print(f"[-] Tab {tab_index} Scraper error: {e}\n{traceback.format_exc()}")
                if self.context:
                    self.context.log("error", f"[-] Tab {tab_index} Scraper error: {e}\n{traceback.format_exc()}")
                err_str = str(e).lower()
                if "closed" in err_str or "target" in err_str or "navigation" in err_str:
                    self.context.tab_states[tab_index]["status"] = "closed"
                else:
                    self.context.tab_states[tab_index]["status"] = "failed"
            finally:
                if 'page' in locals() and page:
                    try:
                        page.remove_listener("response", handle_response)
                    except Exception:
                        pass
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass
                if tab_index in self.context.active_pages:
                    del self.context.active_pages[tab_index]
                
                # Only overwrite to "done" if not in a terminal error state
                current_status = self.context.tab_states[tab_index].get("status")
                if current_status not in ("closed", "failed", "expired"):
                    self.context.tab_states[tab_index]["status"] = "done"
                print(f"[+] Tab {tab_index} Scraper dung. Trang thai cuoi: {self.context.tab_states[tab_index]['status']}")
