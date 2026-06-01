# tools/socialpeta_downloader/core/downloader.py
"""
Responsibility: Parallel download workers, deduplication filtering thread, and system controller.
"""

import os
import sys
import time
import json
import shutil
import queue
import subprocess
import requests
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

class DynamicSemaphore:
    """
    A thread-safe semaphore that allows changing the limit dynamically.
    """
    def __init__(self, value=3):
        self.value = value
        self.active_count = 0
        self.cv = threading.Condition()

    def set_value(self, new_value):
        with self.cv:
            self.value = new_value
            self.cv.notify_all()

    def acquire(self):
        with self.cv:
            while self.active_count >= self.value:
                self.cv.wait()
            self.active_count += 1

    def release(self):
        with self.cv:
            self.active_count = max(0, self.active_count - 1)
            self.cv.notify_all()

class DownloaderMixin:
    running: bool
    pause_event: threading.Event
    sys_monitor: Any
    download_semaphore: DynamicSemaphore
    pending_downloads: queue.PriorityQueue
    history_lock: threading.RLock
    download_dir: str
    disk_full: bool
    temp_download_dir: str
    image_md5_cache: dict
    filter_queue: queue.Queue
    tab_running_events: dict

    if TYPE_CHECKING:
        def get_item_lock(self, fpath: str) -> Any: ...
        def _is_ad_already_downloaded(self, ad_id: str) -> bool: ...
        def _is_ad_already_downloading_or_done(self, ad_id: str, exclude_path: Optional[str] = None) -> bool: ...
        def _save_item_state(self, item: dict) -> None: ...
        def append_to_audit_csv(self, ad_id: str, app_name: str, dup_ad_id: str, reason: str) -> None: ...
        def log(self, level: str, message: str) -> None: ...
        def append_to_csv(self, item: dict) -> None: ...
        def _get_file_md5(self, filepath: str) -> Optional[str]: ...
        def get_unique_image_filename(self, app_name: str, url: str) -> tuple[str, int]: ...
        def check_duplicate(self, new_file: str) -> tuple[bool, str, str]: ...
        def get_unique_filename(self, app_name: str) -> tuple[str, int]: ...
        def get_video_duration(self, file_path: str) -> float: ...
        def restore_session(self) -> None: ...


    def download_image_file(self, url: str, dest_path: str) -> bool:
        if not url:
            return False
        if url.startswith("//"):
            url = "https:" + url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.socialpeta.com/"
        }
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=20)
            if response.status_code == 200:
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)
                return True
        except Exception as e:
            self.log("warning", f"Lỗi tải file ảnh: {e}")
        return False

    def _download_worker(self):
        while self.running:
            self.pause_event.wait()
            stats = self.sys_monitor.get_stats()
            if stats.get("ram_usage", 0) > 95.0:
                time.sleep(5)
                continue
            self.download_semaphore.acquire()
            try:
                _, file_path = self.pending_downloads.get(timeout=1.0)
            except queue.Empty:
                self.download_semaphore.release()
                continue
            if not self.running:
                self.download_semaphore.release()
                break
            item = None
            fpath = file_path
            ad_id = os.path.splitext(os.path.basename(fpath))[0]
            lock = self.get_item_lock(fpath)
            if lock.acquire(blocking=False):
                try:
                    if os.path.exists(fpath):
                        with open(fpath, 'r', encoding='utf-8') as f:
                            candidate_item = json.load(f)
                        if candidate_item.get("status") == "pending":
                            item = candidate_item
                except Exception:
                    pass
                if not item:
                    lock.release()
            if not item:
                self.download_semaphore.release()
                continue
            ad_id = item["ad_id"]
            media_type = item.get("media_type", "video")
            item["fpath"] = fpath
            try:
                with self.history_lock:
                    if self._is_ad_already_downloaded(ad_id) or self._is_ad_already_downloading_or_done(ad_id, exclude_path=fpath):
                        item["status"] = "duplicate"
                        self._save_item_state(item)
                        self.append_to_audit_csv(ad_id, item.get("app_name", "UnknownApp"), "", "Duplicate check at start of download")
                        continue

                # Chuẩn hóa và xác thực URL
                video_url = item.get("video_url", "").strip()
                youtube_url = item.get("youtube_url", "").strip()
                image_url = item.get("image_url", "").strip()

                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                if youtube_url.startswith("//"):
                    youtube_url = "https:" + youtube_url
                if image_url.startswith("//"):
                    image_url = "https:" + image_url

                item["video_url"] = video_url
                item["youtube_url"] = youtube_url
                item["image_url"] = image_url

                if media_type in ("video", "youtube_click_required") and not video_url:
                    if youtube_url:
                        self.log("info", f"Ad {ad_id}: video_url rỗng nhưng phát hiện youtube_url. Chuyển đổi sang youtube_video.")
                        media_type = "youtube_video"
                        item["media_type"] = "youtube_video"
                    elif image_url:
                        self.log("info", f"Ad {ad_id}: video_url rỗng nhưng phát hiện image_url. Chuyển đổi sang image.")
                        media_type = "image"
                        item["media_type"] = "image"
                    else:
                        self.log("warning", f"Ad {ad_id}: Cả video_url và youtube_url đều rỗng. Bỏ qua không tải.")
                        item["status"] = "no_media"
                        self._save_item_state(item)
                        self.append_to_csv(item)
                        continue
                try:
                    total, used, free = shutil.disk_usage(self.download_dir)
                    if free < 100 * 1024 * 1024:
                        self.disk_full = True
                        self.log("error", "CẢNH BÁO KHẨN CẤP: Ổ đĩa đầy (< 100MB trống). Tạm dừng download.")
                        self.pause_event.clear()
                        continue
                    else:
                        self.disk_full = False
                except Exception:
                    pass
                print(f"[*] Worker: Bat dau tai media ({media_type}) Ad ID: {ad_id}")
                os.makedirs(self.temp_download_dir, exist_ok=True)
                item["status"] = "downloading"
                self._save_item_state(item)
                self.append_to_csv(item)
                if media_type in ("youtube_thumbnail", "image"):
                    image_url = item.get("image_url")
                    if not image_url:
                        item["status"] = "no_media"
                        self._save_item_state(item)
                        self.append_to_csv(item)
                        continue
                    temp_output = os.path.join(self.temp_download_dir, f"{ad_id}_img.tmp")
                    if os.path.exists(temp_output):
                        try:
                            os.remove(temp_output)
                        except Exception:
                            pass
                    success = self.download_image_file(image_url, temp_output)
                    if success and os.path.exists(temp_output):
                        if os.path.getsize(temp_output) == 0:
                            try:
                                os.remove(temp_output)
                            except Exception:
                                pass
                            item["status"] = "failed"
                            self._save_item_state(item)
                            self.log("error", f"Tải file ảnh cho Ad {ad_id} có kích thước 0 byte.")
                            continue
                        md5_val = self._get_file_md5(temp_output)
                        if md5_val and md5_val in self.image_md5_cache:
                            dup_ad_id = self.image_md5_cache[md5_val]
                            try:
                                os.remove(temp_output)
                            except Exception:
                                pass
                            item["status"] = "duplicate"
                            self._save_item_state(item)
                            self.append_to_audit_csv(ad_id, item.get("app_name", "UnknownApp"), dup_ad_id, f"Image MD5 match with {dup_ad_id}")
                        else:
                            filename, stt = self.get_unique_image_filename(item.get("app_name", "UnknownApp"), image_url)
                            os.makedirs(self.download_dir, exist_ok=True)
                            final_path = os.path.join(self.download_dir, filename)
                            try:
                                shutil.move(temp_output, final_path)
                                if md5_val:
                                    self.image_md5_cache[md5_val] = ad_id
                                item["status"] = "done"
                                item["video_name"] = filename
                                item["saved_path"] = final_path
                                item["file_size"] = os.path.getsize(final_path)
                                item["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                self._save_item_state(item)
                                self.append_to_csv(item)
                            except Exception as e:
                                self.log("error", f"Lỗi di chuyển file ảnh Ad {ad_id}: {e}")
                                item["status"] = "failed"
                                self._save_item_state(item)
                    else:
                        item["status"] = "failed"
                        self._save_item_state(item)
                        self.log("error", f"Tải file ảnh thất bại cho Ad {ad_id}.")
                    continue
                temp_output = os.path.join(self.temp_download_dir, f"{ad_id}.tmp")
                if os.path.exists(temp_output):
                    try:
                        os.remove(temp_output)
                    except Exception:
                        pass
                if media_type == "youtube_video":
                    success = False
                    try:
                        ytdlp_bin = "yt-dlp"
                        venv_bin = os.path.join(os.path.dirname(sys.executable), "yt-dlp.exe")
                        if os.path.exists(venv_bin):
                            ytdlp_bin = venv_bin
                        else:
                            local_venv_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Scripts", "yt-dlp.exe"))
                            if os.path.exists(local_venv_bin):
                                ytdlp_bin = local_venv_bin
                            else:
                                root_venv_bin = os.path.abspath(os.path.join(os.getcwd(), ".venv", "Scripts", "yt-dlp.exe"))
                                if os.path.exists(root_venv_bin):
                                    ytdlp_bin = root_venv_bin
                        cmd = [ytdlp_bin, "-o", temp_output, "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", "--merge-output-format", "mp4", item.get("youtube_url")]
                        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                        if res.returncode == 0 and os.path.exists(temp_output):
                            success = True
                        elif os.path.exists(temp_output + ".mp4"):
                            shutil.move(temp_output + ".mp4", temp_output)
                            success = True
                    except Exception as e:
                        self.log("error", f"yt-dlp failed for Ad {ad_id}: {e}")
                    if success:
                        temp_mp4 = os.path.join(self.temp_download_dir, f"{ad_id}.mp4")
                        if os.path.exists(temp_mp4):
                            os.remove(temp_mp4)
                        shutil.move(temp_output, temp_mp4)
                        item["status"] = "downloaded"
                        item["saved_path"] = temp_mp4
                        item["file_size"] = os.path.getsize(temp_mp4)
                        self._save_item_state(item)
                        self.filter_queue.put(item)
                    else:
                        item["status"] = "failed"
                        self._save_item_state(item)
                        self.log("error", f"Tải YouTube video thất bại cho Ad {ad_id}.")
                    continue
                video_url = item.get("video_url", "").strip()
                if not video_url:
                    item["status"] = "no_media"
                    self._save_item_state(item)
                    self.log("warning", f"Ad {ad_id}: Không tải được CDN vì link video rỗng.")
                    continue
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.socialpeta.com/"
                }
                download_success = False
                backoff = 1.0
                for attempt in range(4):
                    if not self.running:
                        break
                    try:
                        response = requests.get(video_url, headers=headers, stream=True, timeout=20)
                        if response.status_code == 403:
                            item["status"] = "expired"
                            self._save_item_state(item)
                            self.log("error", f"Link CDN đã hết hạn (403 Forbidden) cho Ad {ad_id}.")
                            self.append_to_csv(item)
                            break
                        response.raise_for_status()
                        with open(temp_output, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=16384):
                                if not self.running or not chunk:
                                    break
                                f.write(chunk)
                        if self.running:
                            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                                download_success = True
                                break
                            else:
                                if os.path.exists(temp_output):
                                    os.remove(temp_output)
                    except Exception as ex:
                        self.log("error", f"Lỗi tải video CDN cho Ad {ad_id} (Lần thử {attempt+1}): {ex}")
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                    if attempt < 3:
                        time.sleep(backoff)
                        backoff *= 2
                if download_success:
                    temp_mp4 = os.path.join(self.temp_download_dir, f"{ad_id}.mp4")
                    if os.path.exists(temp_mp4):
                        os.remove(temp_mp4)
                    shutil.move(temp_output, temp_mp4)
                    item["status"] = "downloaded"
                    item["saved_path"] = temp_mp4
                    item["file_size"] = os.path.getsize(temp_mp4)
                    self._save_item_state(item)
                    self.filter_queue.put(item)
                else:
                    if item["status"] != "expired":
                        item["status"] = "failed"
                        self._save_item_state(item)
                        self.log("error", f"Tải file video CDN thất bại cho Ad {ad_id} sau các lần thử.")
            except Exception as e:
                self.log("error", f"Lỗi không xác định trong download worker cho Ad {ad_id}: {e}")
            finally:
                lock = self.get_item_lock(fpath)
                try:
                    lock.release()
                except RuntimeError:
                    pass
                self.download_semaphore.release()

    def stream_3_dedup_filter(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            self.log("error", "Lỗi: ffprobe/ffmpeg chưa được cài đặt!")
            return
        while self.running:
            try:
                item = self.filter_queue.get(timeout=2.0)
            except queue.Empty:
                continue
            ad_id = "unknown"
            try:
                if not isinstance(item, dict):
                    continue
                ad_id = item.get("ad_id", "unknown")
                temp_path = item.get("saved_path", "")
                if not os.path.exists(temp_path):
                    continue
                is_dup, dup_ad_id, reason = self.check_duplicate(temp_path)
                if is_dup:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                    item["status"] = "duplicate"
                    item["saved_path"] = ""
                    self._save_item_state(item)
                    self.append_to_audit_csv(ad_id, item["app_name"], dup_ad_id, reason)
                else:
                    final_filename, stt = self.get_unique_filename(item["app_name"])
                    os.makedirs(self.download_dir, exist_ok=True)
                    final_path = os.path.join(self.download_dir, final_filename)
                    try:
                        if os.path.exists(final_path):
                            os.remove(final_path)
                        shutil.move(temp_path, final_path)
                        actual_dur = self.get_video_duration(final_path)
                        if actual_dur > 0:
                            item["duration"] = actual_dur
                        item["status"] = "done"
                        item["video_name"] = final_filename
                        item["saved_path"] = final_path
                        item["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self._save_item_state(item)
                        self.append_to_csv(item)
                    except Exception as e:
                        self.log("error", f"Lỗi di chuyển file unique cho Ad {ad_id}: {e}")
                        item["status"] = "failed"
                        self._save_item_state(item)
            except Exception as outer_e:
                self.log("error", f"Lỗi ở bộ lọc trùng lặp video Ad {ad_id}: {outer_e}")
                try:
                    if 'item' in locals() and isinstance(item, dict):
                        item["status"] = "failed"
                        self._save_item_state(item)
                except Exception:
                    pass

    def start_system(self, thread_count=3):
        import threading
        if self.running:
            return
        self.running = True
        self.sys_monitor.max_threads_user = thread_count
        self.sys_monitor.start()
        stats = self.sys_monitor.get_stats()
        if stats.get("low_ram_system", False):
            thread_count = min(2, thread_count)
        self.download_semaphore.set_value(thread_count)
        self.restore_session()
        self.download_threads = []
        for _ in range(thread_count):
            t = threading.Thread(target=self._download_worker, daemon=True)
            t.start()
            self.download_threads.append(t)
        self.dedup_thread = threading.Thread(target=self.stream_3_dedup_filter, daemon=True)
        self.dedup_thread.start()
        self.monitor_control_thread = threading.Thread(target=self._system_control_loop, daemon=True)
        self.monitor_control_thread.start()

    def stop_system(self):
        self.running = False
        self.pause_event.set()
        self.sys_monitor.stop()
        for idx in list(self.tab_running_events.keys()):
            self.tab_running_events[idx].clear()
        self.download_semaphore.set_value(99)
        time.sleep(2)

    def _system_control_loop(self):
        while self.running:
            stats = self.sys_monitor.get_stats()
            recommended = stats["max_threads_recommended"]
            if self.download_semaphore.value != recommended:
                self.download_semaphore.set_value(recommended)
            time.sleep(5)
