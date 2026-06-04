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
from socialpeta_downloader.core.protocols import IEngineContext

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

class UtilsService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def log(self, level: str, message: str):
        msg = {
            "type": level,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": message
        }
        if self.context:
            self.context.log_queue.put(msg)
            with self.context.log_subscribers_lock:
                for sub_queue in self.context.log_subscribers:
                    try:
                        sub_queue.put_nowait(msg)
                    except Exception:
                        pass
            if getattr(self.context, "quiet_mode", False):
                return
        print(f"[{level.upper()}] {message}")

    def clear_logs(self):
        if not self.context:
            return
        while not self.context.log_queue.empty():
            try:
                self.context.log_queue.get_nowait()
            except Exception:
                break
        with self.context.log_subscribers_lock:
            for sub_queue in self.context.log_subscribers:
                while not sub_queue.empty():
                    try:
                        sub_queue.get_nowait()
                    except Exception:
                        break

    def get_item_lock(self, fpath: str) -> Any:
        # RefCountedLock expects the lock dict and lock object from the context
        item_locks = self.context.item_locks if self.context else {}
        item_locks_lock = self.context.item_locks_lock if self.context else threading.Lock()
        return RefCountedLock(fpath, item_locks, item_locks_lock)

    def get_relative_path(self, path: str) -> str:
        """
        Converts an absolute path to a relative path from the current download_dir.
        If the path is already relative, or cannot be made relative to the download_dir,
        returns the path normalized.
        """
        if not path:
            return ""
        if not self.context or not getattr(self.context, "download_dir", None):
            return os.path.normpath(path)
            
        norm_path = os.path.abspath(path)
        norm_dl_dir = os.path.abspath(self.context.download_dir)
        
        # Check if norm_path is inside norm_dl_dir
        if norm_path.startswith(norm_dl_dir):
            rel = os.path.relpath(norm_path, norm_dl_dir)
            # Use forward slashes for relative path consistency
            return rel.replace("\\", "/")
            
        return os.path.normpath(path)

    def resolve_saved_path(self, path: str) -> str:
        """
        Resolves a saved path (which might be relative) back to an absolute path.
        If the path is relative, resolves it relative to the current download_dir.
        If it's already absolute, returns it as-is.
        """
        if not path:
            return ""
        if os.path.isabs(path):
            return os.path.normpath(path)
            
        if not self.context or not getattr(self.context, "download_dir", None):
            return os.path.abspath(path)
            
        return os.path.normpath(os.path.join(self.context.download_dir, path))

    def get_db_path(self) -> str:
        if self.context and getattr(self.context, "download_dir", None):
            return os.path.join(self.context.download_dir, "db.sqlite3")
        return os.path.join(settings.DATA_DIR, "db.sqlite3")

    def db_get_item(self, ad_id: str) -> Optional[dict]:
        import sqlite3
        db_path = self.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT item_json FROM ad_metadata WHERE ad_id = ?", (ad_id,))
            row = cursor.fetchone()
            if row:
                item = json.loads(row[0])
                if item.get("saved_path"):
                    item["saved_path"] = self.resolve_saved_path(item["saved_path"])
                return item
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error db_get_item for {ad_id}: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
        return None

    def db_get_item_by_fpath(self, fpath: str) -> Optional[dict]:
        import sqlite3
        db_path = self.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT item_json FROM ad_metadata WHERE fpath = ?", (fpath,))
            row = cursor.fetchone()
            if row:
                item = json.loads(row[0])
                if item.get("saved_path"):
                    item["saved_path"] = self.resolve_saved_path(item["saved_path"])
                return item
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error db_get_item_by_fpath for {fpath}: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
        return None

    def _write_item_file(self, fpath: str, item: dict):
        import sqlite3
        db_path = self.get_db_path()
        ad_id = item.get("ad_id")
        if not ad_id:
            return
            
        if not fpath:
            temp_queue_dir = self.context.temp_queue_dir if self.context else "data/.temp"
            api_dir = os.path.join(temp_queue_dir, "api")
            os.makedirs(api_dir, exist_ok=True)
            fpath = os.path.join(api_dir, f"{ad_id}.json")
            item["fpath"] = fpath
            
        status = item.get("status", "pending")
        
        # Create a copy to avoid mutating the live item in-place
        item_copy = dict(item)
        if item_copy.get("saved_path"):
            item_copy["saved_path"] = self.get_relative_path(item_copy["saved_path"])
            
        item_json = json.dumps(item_copy, ensure_ascii=False)
        
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ad_metadata (ad_id, fpath, status, item_json, mtime)
                VALUES (?, ?, ?, ?, ?)
            """, (ad_id, fpath, status, item_json, time.time()))
            conn.commit()
            
            if self.context:
                old_status = self.context.item_status_cache.get(fpath)
                new_status = status
                if old_status != new_status:
                    with self.context.stats_lock:
                        if not old_status:
                            self.context.stats["total_sniffed"] += 1
                        if old_status and old_status in self.context.stats:
                            self.context.stats[old_status] = max(0, self.context.stats[old_status] - 1)
                        if new_status in self.context.stats:
                            self.context.stats[new_status] += 1
                
                self.context.item_status_cache[fpath] = new_status
                self.context.ad_id_to_status[ad_id] = new_status
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error writing SQLite ad_metadata for {ad_id}: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()

    def _save_item_state(self, item: dict):
        fpath = item.get("fpath")
        if not fpath:
            temp_queue_dir = self.context.temp_queue_dir if self.context else "data/.temp"
            api_dir = os.path.join(temp_queue_dir, "api")
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
        
        stt = 1
        if self.context:
            with self.context.stt_lock:
                stt = self.context.stt_counter
                self.context.stt_counter += 1
            
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
        stt = 1
        if self.context:
            with self.context.stt_lock:
                stt = self.context.stt_counter
                self.context.stt_counter += 1
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
        import sqlite3
        data = {}
        db_path = self.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ad_id, item_json FROM ad_metadata")
            for ad_id, item_json in cursor.fetchall():
                try:
                    data[ad_id] = json.loads(item_json)
                except Exception as ex:
                    import traceback
                    self.log("error", f"[-] Error decoding JSON for ad_id {ad_id}: {ex}\n{traceback.format_exc()}")
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error reading all metadata from SQLite: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
        return data

    def _is_ad_already_downloaded(self, ad_id: str) -> bool:
        if self.context:
            status = self.context.ad_id_to_status.get(ad_id)
            if status in ("done", "downloaded"):
                return True
                
        import sqlite3
        db_path = self.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT saved_path, file_size FROM download_history WHERE ad_id = ?", (ad_id,))
            row = cursor.fetchone()
            if row:
                saved_path, file_size = row
                try:
                    fsize = int(file_size or "0")
                except ValueError:
                    fsize = 0
                resolved_path = self.resolve_saved_path(saved_path)
                if resolved_path and os.path.exists(resolved_path) and fsize > 0:
                    if self.context:
                        self.context.ad_id_to_status[ad_id] = "done"
                    return True
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error checking ad download in SQLite: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
        return False

    def _is_ad_already_downloading_or_done(self, ad_id: str, exclude_path: Optional[str] = None) -> bool:
        if self._is_ad_already_downloaded(ad_id):
            return True
        if self.context:
            status = self.context.ad_id_to_status.get(ad_id)
            if status in ("downloading", "done", "downloaded"):
                return True
        return False

    def _get_playwright_context(self, p):
        session_dir = self.context.session_dir if self.context else "data/session"
        state_file = os.path.join(session_dir, "storage_state.json")
        return p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
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
            f"li:has-text('{page_num}')"
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

    def _recursive_find_creatives(self, obj) -> List[dict]:
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
                      "youtube" in video_url.lower() or "youtu.be" in video_url.lower() or "youtube-nocookie.com" in video_url.lower() or
                      "youtube" in youtube_url.lower() or "youtu.be" in youtube_url.lower() or "youtube-nocookie.com" in youtube_url.lower() or
                      (not video_url and not youtube_url and "youtube" in publisher.lower()))
                      
        if is_youtube:
            print(f"[YouTube] ad_key={ad_id} platform={platform}")

        if not video_url and image_url and not is_youtube:
            media_type = "image"
        elif is_youtube:
            is_real_youtube_link = (
                (youtube_url and ("youtube" in youtube_url.lower() or "youtu.be" in youtube_url.lower() or "youtube-nocookie.com" in youtube_url.lower())) or
                (video_url and ("youtube" in video_url.lower() or "youtu.be" in video_url.lower() or "youtube-nocookie.com" in video_url.lower()))
            )
            if is_real_youtube_link:
                media_type = "youtube_video"
            elif not youtube_url and video_url and not ("youtube" in video_url.lower() or "youtu.be" in video_url.lower() or "youtube-nocookie.com" in video_url.lower()):
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

