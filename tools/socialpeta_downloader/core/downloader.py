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
from typing import Any, Optional
from socialpeta_downloader.config import settings
from socialpeta_downloader.core.protocols import IEngineContext

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

class DownloaderService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context
        self.download_threads = []
        self.dedup_thread = None
        self.monitor_control_thread = None

    def download_image_file(self, url: str, dest_path: str) -> bool:
        if not self.context:
            return False
            
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
            import traceback
            self.context.utils_service.log("warning", f"Lỗi tải file ảnh: {e}\n{traceback.format_exc()}")
        return False

    def _download_worker(self):
        if not self.context:
            return
            
        while self.context.running:
            self.context.pause_event.wait()
            stats = self.context.sys_monitor.get_stats()
            if stats.get("ram_usage", 0) > 95.0:
                time.sleep(5)
                continue
            self.context.download_semaphore.acquire()
            try:
                _, file_path = self.context.pending_downloads.get(timeout=1.0)
            except queue.Empty:
                self.context.download_semaphore.release()
                continue
            if not self.context.running:
                self.context.download_semaphore.release()
                break
            item = None
            fpath = file_path
            ad_id = os.path.splitext(os.path.basename(fpath))[0]
            lock = self.context.get_item_lock(fpath)
            if lock.acquire(blocking=False):
                try:
                    candidate_item = self.context.db_get_item_by_fpath(fpath)
                    if candidate_item and candidate_item.get("status") == "pending":
                        item = candidate_item
                except Exception as e:
                    import traceback
                    self.context.log("error", f"[-] Error querying metadata in downloader worker thread: {e}\n{traceback.format_exc()}")
                if not item:
                    lock.release()
            if not item:
                self.context.download_semaphore.release()
                continue
            ad_id = item["ad_id"]
            media_type = item.get("media_type", "video")
            item["fpath"] = fpath
            try:
                with self.context.history_lock:
                    if (self.context.utils_service._is_ad_already_downloaded(ad_id) or 
                        self.context.utils_service._is_ad_already_downloading_or_done(ad_id, exclude_path=fpath)):
                        item["status"] = "duplicate"
                        self.context.utils_service._save_item_state(item)
                        self.context.session_service.append_to_audit_csv(
                            ad_id, item.get("app_name", "UnknownApp"), "", "Duplicate check at start of download"
                        )
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
                        self.context.utils_service.log("info", f"Ad {ad_id}: video_url rỗng nhưng phát hiện youtube_url. Chuyển đổi sang youtube_video.")
                        media_type = "youtube_video"
                        item["media_type"] = "youtube_video"
                    elif image_url:
                        self.context.utils_service.log("info", f"Ad {ad_id}: video_url rỗng nhưng phát hiện image_url. Chuyển đổi sang image.")
                        media_type = "image"
                        item["media_type"] = "image"
                    else:
                        self.context.utils_service.log("warning", f"Ad {ad_id}: Cả video_url và youtube_url đều rỗng. Bỏ qua không tải.")
                        item["status"] = "no_media"
                        self.context.utils_service._save_item_state(item)
                        self.context.session_service.append_to_csv(item)
                        continue
                
                download_mode = getattr(self.context, "download_mode", "all")
                if download_mode == "image":
                    if media_type not in ("image", "youtube_thumbnail"):
                        self.context.utils_service.log("info", f"Ad {ad_id}: Bỏ qua do chế độ Chỉ tải ảnh.")
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                        continue
                elif download_mode == "youtube":
                    if media_type not in ("youtube_video", "youtube_click_required"):
                        self.context.utils_service.log("info", f"Ad {ad_id}: Bỏ qua do chế độ Chỉ tải video YouTube.")
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                        continue
                        
                try:
                    total, used, free = shutil.disk_usage(self.context.download_dir)
                    if free < 100 * 1024 * 1024:
                        self.context.disk_full = True
                        self.context.utils_service.log("error", "CẢNH BÁO KHẨN CẤP: Ổ đĩa đầy (< 100MB trống). Tạm dừng download.")
                        self.context.pause_event.clear()
                        continue
                    else:
                        self.context.disk_full = False
                except Exception as e:
                    import traceback
                    self.context.utils_service.log("warning", f"Lỗi kiểm tra dung lượng đĩa: {e}\n{traceback.format_exc()}")
                print(f"[*] Worker: Bat dau tai media ({media_type}) Ad ID: {ad_id}")
                os.makedirs(self.context.temp_download_dir, exist_ok=True)
                item["status"] = "downloading"
                self.context.utils_service._save_item_state(item)
                self.context.session_service.append_to_csv(item)
                
                if media_type in ("youtube_thumbnail", "image"):
                    image_url = item.get("image_url")
                    if not image_url:
                        item["status"] = "no_media"
                        self.context.utils_service._save_item_state(item)
                        self.context.session_service.append_to_csv(item)
                        continue
                    temp_output = os.path.join(self.context.temp_download_dir, f"{ad_id}_img.tmp")
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
                            self.context.utils_service._save_item_state(item)
                            self.context.utils_service.log("error", f"Tải file ảnh cho Ad {ad_id} có kích thước 0 byte.")
                            continue
                        md5_val = self.context.deduplication_service._get_file_md5(temp_output)
                        if md5_val and md5_val in self.context.image_md5_cache:
                            dup_ad_id = self.context.image_md5_cache[md5_val]
                            try:
                                os.remove(temp_output)
                            except Exception:
                                pass
                            item["status"] = "duplicate"
                            self.context.utils_service._save_item_state(item)
                            self.context.session_service.append_to_audit_csv(
                                ad_id, item.get("app_name", "UnknownApp"), dup_ad_id, f"Image MD5 match with {dup_ad_id}"
                            )
                        else:
                            filename, stt = self.context.utils_service.get_unique_image_filename(
                                item.get("app_name", "UnknownApp"), image_url
                            )
                            target_dir = item.get("subfolder_path") or self.context.download_dir
                            os.makedirs(target_dir, exist_ok=True)
                            final_path = os.path.join(target_dir, filename)
                            try:
                                shutil.move(temp_output, final_path)
                                if md5_val:
                                    self.context.image_md5_cache[md5_val] = ad_id
                                item["status"] = "done"
                                item["video_name"] = filename
                                item["saved_path"] = final_path
                                item["file_size"] = os.path.getsize(final_path)
                                item["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                self.context.utils_service._save_item_state(item)
                                json_copy_path = os.path.splitext(final_path)[0] + ".json"
                                self.context._write_item_file(json_copy_path, item)
                                self.context.session_service.append_to_csv(item)
                            except Exception as e:
                                import traceback
                                self.context.utils_service.log("error", f"Lỗi di chuyển file ảnh Ad {ad_id}: {e}\n{traceback.format_exc()}")
                                item["status"] = "failed"
                                self.context.utils_service._save_item_state(item)
                    else:
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                        self.context.utils_service.log("error", f"Tải file ảnh thất bại cho Ad {ad_id}.")
                    continue
                
                temp_output = os.path.join(self.context.temp_download_dir, f"{ad_id}.tmp")
                if os.path.exists(temp_output):
                    try:
                        os.remove(temp_output)
                    except Exception:
                        pass
                        
                if media_type == "youtube_video":
                    success = False
                    try:
                        import yt_dlp
                        ydl_opts = {
                            'outtmpl': temp_output,
                            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                            'merge_output_format': 'mp4',
                            'quiet': True,
                            'no_warnings': True,
                        }
                        ffmpeg_path = settings.FFMPEG_PATH
                        if ffmpeg_path and ffmpeg_path != "ffmpeg":
                            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_path)
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([item.get("youtube_url")])
                        if os.path.exists(temp_output):
                            success = True
                        elif os.path.exists(temp_output + ".mp4"):
                            shutil.move(temp_output + ".mp4", temp_output)
                            success = True
                    except Exception as e:
                        import traceback
                        self.context.utils_service.log("error", f"yt-dlp failed for Ad {ad_id}: {e}\n{traceback.format_exc()}")
                    if success:
                        temp_mp4 = os.path.join(self.context.temp_download_dir, f"{ad_id}.mp4")
                        if os.path.exists(temp_mp4):
                            os.remove(temp_mp4)
                        shutil.move(temp_output, temp_mp4)
                        item["status"] = "downloaded"
                        item["saved_path"] = temp_mp4
                        item["file_size"] = os.path.getsize(temp_mp4)
                        self.context.utils_service._save_item_state(item)
                        self.context.filter_queue.put(item)
                    else:
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                        self.context.utils_service.log("error", f"Tải YouTube video thất bại cho Ad {ad_id}.")
                    continue
                
                video_url = item.get("video_url", "").strip()
                if not video_url:
                    item["status"] = "no_media"
                    self.context.utils_service._save_item_state(item)
                    self.context.utils_service.log("warning", f"Ad {ad_id}: Không tải được CDN vì link video rỗng.")
                    continue
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.socialpeta.com/"
                }
                download_success = False
                backoff = 1.0
                for attempt in range(4):
                    if not self.context.running:
                        break
                    try:
                        response = requests.get(video_url, headers=headers, stream=True, timeout=20)
                        try:
                            if response.raw and response.raw.connection and response.raw.connection.sock:
                                response.raw.connection.sock.settimeout(20.0)
                        except Exception:
                            pass
                        if response.status_code == 403:
                            item["status"] = "expired"
                            self.context.utils_service._save_item_state(item)
                            self.context.utils_service.log("error", f"Link CDN đã hết hạn (403 Forbidden) cho Ad {ad_id}.")
                            self.context.session_service.append_to_csv(item)
                            break
                        response.raise_for_status()
                        with open(temp_output, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=16384):
                                if not self.context.running or not chunk:
                                    break
                                f.write(chunk)
                        if self.context.running:
                            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                                download_success = True
                                break
                            else:
                                if os.path.exists(temp_output):
                                    os.remove(temp_output)
                    except Exception as ex:
                        import traceback
                        self.context.utils_service.log("error", f"Lỗi tải video CDN cho Ad {ad_id} (Lần thử {attempt+1}): {ex}\n{traceback.format_exc()}")
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                    if attempt < 3:
                        time.sleep(backoff)
                        backoff *= 2
                if download_success:
                    temp_mp4 = os.path.join(self.context.temp_download_dir, f"{ad_id}.mp4")
                    if os.path.exists(temp_mp4):
                        os.remove(temp_mp4)
                    shutil.move(temp_output, temp_mp4)
                    item["status"] = "downloaded"
                    item["saved_path"] = temp_mp4
                    item["file_size"] = os.path.getsize(temp_mp4)
                    self.context.utils_service._save_item_state(item)
                    self.context.filter_queue.put(item)
                else:
                    if item["status"] != "expired":
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                        self.context.utils_service.log("error", f"Tải file video CDN thất bại cho Ad {ad_id} sau các lần thử.")
            except Exception as e:
                import traceback
                self.context.utils_service.log("error", f"Lỗi không xác định trong download worker cho Ad {ad_id}: {e}\n{traceback.format_exc()}")
            finally:
                lock = self.context.get_item_lock(fpath)
                try:
                    lock.release()
                except RuntimeError:
                    pass
                self.context.download_semaphore.release()

    def stream_3_dedup_filter(self):
        if not self.context:
            return
            
        try:
            subprocess.run([settings.FFMPEG_PATH, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.0)
            subprocess.run([settings.FFPROBE_PATH, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.0)
        except Exception as e:
            import traceback
            self.context.utils_service.log("error", f"Lỗi: ffprobe/ffmpeg chưa được cài đặt hoặc bị lỗi! Sẽ bỏ qua lọc trùng nâng cao. (Đường dẫn: {settings.FFMPEG_PATH} / {settings.FFPROBE_PATH}): {e}\n{traceback.format_exc()}")
            
        while self.context.running:
            try:
                item = self.context.filter_queue.get(timeout=2.0)
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
                
                # Check binaries availability and run capability at processing time
                binaries_available = True
                try:
                    subprocess.run([settings.FFMPEG_PATH, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.0)
                    subprocess.run([settings.FFPROBE_PATH, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.0)
                except Exception:
                    binaries_available = False
                
                is_dup = False
                dup_ad_id = ""
                reason = ""
                if binaries_available:
                    is_dup, dup_ad_id, reason = self.context.deduplication_service.check_duplicate(temp_path)
                else:
                    self.context.utils_service.log("error", f"Bỏ qua bước trùng lặp cho Ad {ad_id}: ffmpeg hoặc ffprobe không khả dụng (đã bị xóa, lỗi hoặc mất quyền chạy).")
                    item["dedup_checked"] = False
                    item["dedup_status"] = "chưa kiểm tra trùng lặp"
                
                if binaries_available and is_dup:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                    item["status"] = "duplicate"
                    item["saved_path"] = ""
                    item["dedup_checked"] = True
                    item["dedup_status"] = "trùng lặp"
                    self.context.utils_service._save_item_state(item)
                    self.context.session_service.append_to_audit_csv(ad_id, item["app_name"], dup_ad_id, reason)
                else:
                    final_filename, stt = self.context.utils_service.get_unique_filename(item["app_name"])
                    target_dir = item.get("subfolder_path") or self.context.download_dir
                    os.makedirs(target_dir, exist_ok=True)
                    final_path = os.path.join(target_dir, final_filename)
                    try:
                        if os.path.exists(final_path):
                            os.remove(final_path)
                        shutil.move(temp_path, final_path)
                        actual_dur = 0
                        if binaries_available:
                            actual_dur = self.context.deduplication_service.get_video_duration(final_path)
                        if actual_dur > 0:
                            item["duration"] = actual_dur
                        item["status"] = "done"
                        item["video_name"] = final_filename
                        item["saved_path"] = final_path
                        item["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if binaries_available:
                            item["dedup_checked"] = True
                            item["dedup_status"] = "không trùng lặp"
                        self.context.utils_service._save_item_state(item)
                        json_copy_path = os.path.splitext(final_path)[0] + ".json"
                        self.context._write_item_file(json_copy_path, item)
                        self.context.session_service.append_to_csv(item)
                    except Exception as e:
                        import traceback
                        self.context.utils_service.log("error", f"Lỗi di chuyển file unique cho Ad {ad_id}: {e}\n{traceback.format_exc()}")
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
            except Exception as outer_e:
                import traceback
                self.context.utils_service.log("error", f"Lỗi ở bộ lọc trùng lặp video Ad {ad_id}: {outer_e}\n{traceback.format_exc()}")
                try:
                    if 'item' in locals() and isinstance(item, dict):
                        item["status"] = "failed"
                        self.context.utils_service._save_item_state(item)
                except Exception:
                    pass

    def start_system(self, thread_count=3):
        if not self.context:
            return
            
        if self.context.running:
            return
            
        self.context.running = True
        self.context.sys_monitor.max_threads_user = thread_count
        self.context.sys_monitor.start()
        stats = self.context.sys_monitor.get_stats()
        if stats.get("low_ram_system", False):
            thread_count = min(2, thread_count)
        self.context.download_semaphore.set_value(thread_count)
        self.context.session_service.restore_session()
        
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
        if not self.context:
            return
            
        self.context.running = False
        self.context.pause_event.set()
        self.context.sys_monitor.stop()
        for idx in list(self.context.tab_running_events.keys()):
            self.context.tab_running_events[idx].clear()
        self.context.download_semaphore.set_value(99)
        time.sleep(2)

    def _system_control_loop(self):
        if not self.context:
            return
            
        while self.context.running:
            stats = self.context.sys_monitor.get_stats()
            recommended = stats["max_threads_recommended"]
            if self.context.download_semaphore.value != recommended:
                self.context.download_semaphore.set_value(recommended)
            time.sleep(5)
