# tools/socialpeta_downloader/core/utils.py
"""
Responsibility: Utility helper functions, logging, file and directory management, and UI click handlers.
"""

import os
import sys
import re
import json
import time
import csv
import threading
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from socialpeta_downloader.config import settings

class SafeStreamWrapper:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, data):
        if not self.original_stream:
            return
        try:
            self.original_stream.write(data)
        except UnicodeEncodeError:
            try:
                if hasattr(self.original_stream, 'buffer'):
                    self.original_stream.buffer.write(data.encode('utf-8'))
                else:
                    self.original_stream.write(data.encode('ascii', errors='backslashreplace').decode('ascii'))
            except Exception:
                try:
                    self.original_stream.write(data.encode('ascii', errors='ignore').decode('ascii'))
                except Exception:
                    pass

    def flush(self):
        if self.original_stream and hasattr(self.original_stream, 'flush'):
            try:
                self.original_stream.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self.original_stream, name)

if sys.stdout is not None and not isinstance(sys.stdout, SafeStreamWrapper):
    sys.stdout = SafeStreamWrapper(sys.stdout)
if sys.stderr is not None and not isinstance(sys.stderr, SafeStreamWrapper):
    sys.stderr = SafeStreamWrapper(sys.stderr)

class RefCountedLock:
    def __init__(self, fpath: str, item_locks: dict, item_locks_lock: threading.Lock):
        self.fpath = fpath
        self.item_locks = item_locks
        self.item_locks_lock = item_locks_lock
        with self.item_locks_lock:
            if self.fpath not in self.item_locks:
                self.item_locks[self.fpath] = [threading.RLock(), 0]
            self.lock_info = self.item_locks[self.fpath]
            self.lock_info[1] += 1
            self.lock = self.lock_info[0]

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        return self.lock.acquire(blocking, timeout)

    def release(self) -> None:
        self.lock.release()

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()
        with self.item_locks_lock:
            self.lock_info[1] -= 1
            if self.lock_info[1] <= 0:
                if self.item_locks.get(self.fpath) is self.lock_info:
                    self.item_locks.pop(self.fpath, None)

def is_socialpeta_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return "socialpeta.com" in u or "guangdada.com" in u

class UtilsMixin:
    log_queue: Any
    log_subscribers: list
    log_subscribers_lock: threading.Lock
    item_locks: dict
    item_locks_lock: threading.Lock
    item_status_cache: dict
    stats: dict
    stats_lock: threading.Lock
    ad_id_to_status: dict
    temp_queue_dir: str
    stt_lock: threading.RLock
    stt_counter: int
    csv_path: str
    metadata_lock: threading.RLock
    session_dir: str

    def log(self, level: str, message: str):
        msg = {
            "type": level,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": message
        }
        self.log_queue.put(msg)
        with self.log_subscribers_lock:
            for sub_queue in self.log_subscribers:
                try:
                    sub_queue.put_nowait(msg)
                except Exception:
                    pass
        print(f"[{level.upper()}] {message}")

    def clear_logs(self):
        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except Exception:
                break
        with self.log_subscribers_lock:
            for sub_queue in self.log_subscribers:
                while not sub_queue.empty():
                    try:
                        sub_queue.get_nowait()
                    except Exception:
                        break

    def get_item_lock(self, fpath: str) -> Any:
        return RefCountedLock(fpath, self.item_locks, self.item_locks_lock)

    def _write_item_file(self, fpath: str, item: dict):
        import shutil
        tmp_path = fpath + ".tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=4, ensure_ascii=False)
            shutil.move(tmp_path, fpath)
            
            old_status = self.item_status_cache.get(fpath)
            new_status = item.get("status", "pending")
            if old_status != new_status:
                with self.stats_lock:
                    if old_status and old_status in self.stats:
                        self.stats[old_status] = max(0, self.stats[old_status] - 1)
                    if new_status in self.stats:
                        self.stats[new_status] += 1
            
            self.item_status_cache[fpath] = new_status
            ad_id = item.get("ad_id")
            if ad_id:
                self.ad_id_to_status[ad_id] = new_status
        except Exception as e:
            print(f"[-] Error writing item file {fpath}: {e}")

    def _save_item_state(self, item: dict):
        fpath = item.get("fpath")
        if not fpath:
            api_dir = os.path.join(self.temp_queue_dir, "api")
            os.makedirs(api_dir, exist_ok=True)
            fpath = os.path.join(api_dir, f"{item['ad_id']}.json")
            item["fpath"] = fpath
            
        lock = self.get_item_lock(fpath)
        with lock:
            self._write_item_file(fpath, item)

    def clean_app_name(self, app_name: str) -> str:
        if not app_name:
            return "UnknownApp"
        
        part = re.split(r'[-:|]', app_name)[0].strip()
        if not part:
            return "UnknownApp"
            
        cleaned = re.sub(r'[^\w\s]', '', part)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        if not cleaned:
            return "UnknownApp"
            
        stopwords = {"by", "for", "app", "the", "with", "pro", "lite", "plus"}
        words = cleaned.split()
        while words and words[-1].lower() in stopwords:
            words.pop()
            
        if not words:
            return "UnknownApp"
            
        if len(words) >= 2:
            w1 = words[0][0].upper() + words[0][1:] if len(words[0]) > 1 else words[0].upper()
            w2 = words[1][0].upper() + words[1][1:] if len(words[1]) > 1 else words[1].upper()
            return w1 + w2
        else:
            single_word = words[0]
            cjk_chars = re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', single_word)
            if cjk_chars and len(single_word) >= 2:
                return single_word[:2]
            return single_word[0].upper() + single_word[1:] if len(single_word) > 1 else single_word.upper()

    def get_unique_filename(self, app_name: str) -> tuple[str, int]:
        clean_name = self.clean_app_name(app_name)
        date_str = datetime.now().strftime("%d%m%Y")
        
        with self.stt_lock:
            stt = self.stt_counter
            self.stt_counter += 1
            
        filename = f"{clean_name}_SPY_{date_str}_{stt}.mp4"
        return filename, stt

    def get_unique_image_filename(self, app_name: str, url: str) -> tuple[str, int]:
        clean_name = self.clean_app_name(app_name)
        date_str = datetime.now().strftime("%d%m%Y")
        ext = ".jpg"
        if url:
            path_part = url.split("?")[0]
            for e in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                if path_part.lower().endswith(e):
                    ext = e
                    break
        with self.stt_lock:
            stt = self.stt_counter
            self.stt_counter += 1
        filename = f"{clean_name}_SPY_{date_str}_{stt}{ext}"
        return filename, stt

    def clean_filename(self, filename: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", filename)

    def extract_ad_id(self, url: str) -> str:
        match = re.search(r"[?&]id=([^&]+)", url)
        if match:
            return match.group(1)
        parts = url.split("/")
        if parts:
            last = parts[-1].split("?")[0]
            if last.isdigit() or len(last) > 10:
                return last
        return ""


    def _read_temp_json(self) -> dict:
        data = {}
        if not os.path.exists(self.temp_queue_dir):
            return data
        try:
            subdirs = [d for d in os.listdir(self.temp_queue_dir) if d.startswith("tab") or d == "api"]
            for subdir in subdirs:
                subdir_path = os.path.join(self.temp_queue_dir, subdir)
                if os.path.isdir(subdir_path):
                    for fname in os.listdir(subdir_path):
                        if fname.endswith(".json"):
                            fpath = os.path.join(subdir_path, fname)
                            try:
                                with open(fpath, 'r', encoding='utf-8') as f:
                                    item = json.load(f)
                                    ad_id = item.get("ad_id")
                                    if ad_id:
                                        data[ad_id] = item
                            except Exception:
                                pass
        except Exception:
            pass
        return data

    def _is_ad_already_downloaded(self, ad_id: str) -> bool:
        status = self.ad_id_to_status.get(ad_id)
        if status in ("done", "downloaded"):
            return True
                
        if os.path.exists(self.csv_path):
            try:
                with self.metadata_lock:
                    with open(self.csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get("ad_id") == ad_id:
                                saved_path = row.get("saved_path", "")
                                try:
                                    fsize = int(row.get("file_size", "0") or "0")
                                except ValueError:
                                    fsize = 0
                                if saved_path and fsize > 0:
                                    self.ad_id_to_status[ad_id] = "done"
                                    return True
            except Exception:
                pass
        return False

    def _is_ad_already_downloading_or_done(self, ad_id: str, exclude_path: Optional[str] = None) -> bool:
        if self._is_ad_already_downloaded(ad_id):
            return True
        status = self.ad_id_to_status.get(ad_id)
        if status in ("downloading", "done", "downloaded"):
            return True
        return False

    def _get_playwright_context(self, p):
        state_file = os.path.join(self.session_dir, "storage_state.json")
        return p.chromium.launch_persistent_context(
            user_data_dir=self.session_dir,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            storage_state=state_file if os.path.exists(state_file) else None
        )

    def _click_page_button(self, page, page_num: int) -> bool:
        selectors = [
            f"li.ant-pagination-item-{page_num}",
            f"ul.ant-pagination li.ant-pagination-item-{page_num}",
            f"ul.el-pagination li.number:has-text('{page_num}')",
            f".el-pagination li:has-text('{page_num}')",
            f"//li[contains(@class, 'number') and text()='{page_num}']",
            f"button:has-text('{page_num}')",
            f"li:has-text('{page_num}')",
            f"text=/^{page_num}$/"
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible() and loc.is_enabled():
                    loc.click(timeout=3000)
                    return True
            except Exception:
                continue
        return False

    def _jump_to_page(self, page, page_num: int) -> bool:
        selectors = [
            ".ant-pagination-options-quick-jumper input",
            ".ant-pagination-options input",
            ".ant-pagination input",
            ".el-pagination__jump input",
            "input[type='number']",
            ".el-pagination input"
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible() and loc.is_enabled():
                    loc.click(timeout=3000)
                    loc.fill(str(page_num))
                    loc.press("Enter")
                    return True
            except Exception:
                continue
        print(f"[*] Khong dung duoc o Jump input, thu dung phim mui ten...")
        next_selectors = [
            "li.ant-pagination-next",
            ".ant-pagination-next button",
            "button.btn-next",
            "li.btn-next"
        ]
        for sel in next_selectors:
            try:
                next_btn = page.locator(sel).first
                if next_btn.is_visible() and next_btn.is_enabled():
                    next_btn.click(timeout=3000)
                    return True
            except Exception:
                pass
        return False
