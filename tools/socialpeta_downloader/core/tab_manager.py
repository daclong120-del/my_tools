# tools/socialpeta_downloader/core/tab_manager.py
"""
Responsibility: Multi-tab detection and management. Connects over CDP, injects tab IDs, and manages scraper threads.
"""

import os
import time
import uuid
import queue
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from socialpeta_downloader.config import settings
from playwright.sync_api import sync_playwright
from socialpeta_downloader.core.utils import is_socialpeta_url

class TabManagerMixin:
    # Type declarations to resolve IDE static analysis and linting errors
    tab_id_to_index: Dict[str, int]
    tab_is_new: Dict[str, bool]
    tab_states: Dict[int, Dict[str, Any]]
    tab_running_events: Dict[int, threading.Event]
    tab_packet_received_events: Dict[int, threading.Event]
    tab_last_packet_empty: Dict[int, bool]
    tab_youtube_queues: Dict[int, queue.Queue]
    active_pages: Dict[int, Any]
    running: bool

    if TYPE_CHECKING:
        # Dummy method declarations to prevent IDE unresolved attribute/method warnings
        def ensure_chrome_debug_port(self, port: Optional[int] = None) -> bool:
            ...

        def run_tab_pagination_loop(self, tab_index: int, page: Any, total_pages: int) -> None:
            ...

        def _process_api_response_for_tab(self, tab_index: int, data: dict) -> None:
            ...

        def _youtube_extract_worker_for_tab(self, tab_index: int, page: Any) -> None:
            ...


    def detect_tabs(self, port: Optional[int] = None) -> list:
        """
        Connects to Chrome debug port via HTTP DevTools protocol, detects all SocialPeta tabs,
        and returns a list of active tabs. Fast, lightweight, and prevents CDP session leaks.
        """
        if not self.ensure_chrome_debug_port(port):
            return []
        port_val = port if port is not None else settings.CHROME_DEBUG_PORT
        import requests
        active_tabs = []
        try:
            resp = requests.get(f"http://127.0.0.1:{port_val}/json/list", timeout=3.0)
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
                
                if tab_id not in self.tab_id_to_index:
                    new_idx = len(self.tab_id_to_index) + 1
                    self.tab_id_to_index[tab_id] = new_idx
                    self.tab_is_new[tab_id] = True
                    
                idx = self.tab_id_to_index[tab_id]
                
                if idx not in self.tab_states:
                    self.tab_states[idx] = {
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
                    self.tab_states[idx]["url"] = url
                    self.tab_states[idx]["title"] = title
                    
                active_tabs.append({
                    "index": idx,
                    "tab_id": tab_id,
                    "url": url,
                    "title": title
                })
                
            if not active_tabs:
                print("[*] No active SocialPeta tabs detected. Waiting for user to navigate manually.")
                
            all_assigned_tab_ids = list(self.tab_id_to_index.keys())
            for tid in all_assigned_tab_ids:
                if tid not in current_active_tab_ids:
                    idx = self.tab_id_to_index[tid]
                    if idx in self.tab_running_events:
                        self.tab_running_events[idx].clear()
                    if idx in self.tab_states:
                        self.tab_states[idx]["status"] = "closed"
        except Exception as e:
            print(f"[-] Error detecting tabs: {e}")
            
        return active_tabs

    def _find_page_by_id(self, context, tab_id: str):
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
                    idx = self.tab_id_to_index.get(tab_id)
                    if idx is not None:
                        state = self.tab_states.get(idx)
                        if state and p.url == state.get("url") and p.title() == state.get("title"):
                            return p
            except Exception:
                continue
                
        return None

    def run_tab_scraper(self, tab_index: int, total_pages: int, port: Optional[int] = None):
        import queue
        import re
        from datetime import datetime

        tab_id = self.tab_states[tab_index]["tab_id"]
        url = self.tab_states[tab_index].get("url", "")
        title = self.tab_states[tab_index].get("title", "")
        
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

        # Date string YYYYMMDD
        date_str = datetime.now().strftime("%Y%m%d")

        # Sanitize for safe path name
        ad_network_clean = re.sub(r'[^\w\-]', '', ad_network)
        app_name_clean = re.sub(r'[^\w\-]', '', app_name)
        
        base_name = f"{ad_network_clean}_{app_name_clean}_{date_str}"
        subfolder = base_name
        
        # Deduplication check against active tabs and existing folders
        existing_subfolders = [t.get("subfolder") for t in self.tab_states.values() if t.get("subfolder")]
        counter = 2
        while os.path.exists(os.path.join(self.download_dir, subfolder)) or subfolder in existing_subfolders:
            subfolder = f"{base_name}_{counter}"
            counter += 1

        self.tab_states[tab_index]["subfolder"] = subfolder
        self.tab_states[tab_index]["subfolder_path"] = os.path.join(self.download_dir, subfolder)
        os.makedirs(self.tab_states[tab_index]["subfolder_path"], exist_ok=True)

        print(f"[*] Thread Scraper cho Tab {tab_index} bat dau (Pages: {total_pages})...")
        print(f"[*] Tab {tab_index} duoc gan thu muc: {self.tab_states[tab_index]['subfolder_path']}")
        
        self.tab_states[tab_index]["status"] = "running"
        self.tab_states[tab_index]["target_pages"] = total_pages
        self.tab_running_events[tab_index] = threading.Event()
        self.tab_running_events[tab_index].set()
        
        self.tab_packet_received_events[tab_index] = threading.Event()
        self.tab_last_packet_empty[tab_index] = False
        self.tab_youtube_queues[tab_index] = queue.Queue()
        
        port_val = port if port is not None else settings.CHROME_DEBUG_PORT
        browser = None
        with sync_playwright() as p:
            try:
                for attempt in range(1, 4):
                    try:
                        browser = p.chromium.connect_over_cdp(f"http://localhost:{port_val}")
                        break
                    except Exception as e:
                        if attempt == 3:
                            raise e
                        print(f"[-] Tab {tab_index} CDP connect attempt {attempt} failed: {e}. Retrying in 2s...")
                        time.sleep(2.0)
                if not browser or not browser.contexts:
                    print(f"[-] Tab {tab_index}: Khong tim thay context browser.")
                    self.tab_states[tab_index]["status"] = "failed"
                    return
                context = browser.contexts[0]
                page = self._find_page_by_id(context, tab_id)
                if not page:
                    print(f"[-] Tab {tab_index}: Khong tim thay page voi tab_id={tab_id}")
                    self.tab_states[tab_index]["status"] = "closed"
                    return
                    
                self.active_pages[tab_index] = page
                
                def handle_response(response):
                    url = response.url
                    if response.status in (403, 429, 500):
                        if "/creative/" in url or "/creative-rank/" in url:
                            print(f"[-] Tab {tab_index} API error returned ({response.status}) on: {url}")
                        return
                    if "/creative/list" in url or "/creative-rank/list" in url:
                        try:
                            body = response.json()
                            self._process_api_response_for_tab(tab_index, body)
                        except Exception as ex:
                            print(f"[-] Tab {tab_index} response json error: {ex}")
                            
                page.on("response", handle_response)
                
                if "login" in page.url:
                    print(f"[-] Tab {tab_index}: Yeu cau dang nhap.")
                    self.tab_states[tab_index]["status"] = "expired"
                    return
                    
                self.run_tab_pagination_loop(tab_index, page, total_pages)
                
                q = self.tab_youtube_queues.get(tab_index)
                while self.running and q and not q.empty():
                    if page.is_closed():
                        break
                    self._youtube_extract_worker_for_tab(tab_index, page)
                    time.sleep(0.5)
                
                self.tab_running_events[tab_index].clear()
                    
            except Exception as e:
                print(f"[-] Tab {tab_index} Scraper error: {e}")
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
                if tab_index in self.active_pages:
                    del self.active_pages[tab_index]
                
                # Only overwrite to "done" if not in a terminal error state
                current_status = self.tab_states[tab_index].get("status")
                if current_status not in ("closed", "failed", "expired"):
                    self.tab_states[tab_index]["status"] = "done"
                print(f"[+] Tab {tab_index} Scraper dung. Trang thai cuoi: {self.tab_states[tab_index]['status']}")
