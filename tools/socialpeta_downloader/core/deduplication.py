# tools/socialpeta_downloader/core/deduplication.py
"""
Responsibility: 3-layer video deduplication (Duration, Audio PCM MD5, visual dHash) and image MD5 caching.
"""

import os
import time
import csv
import json
import hashlib
import subprocess
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple
from socialpeta_downloader.config import settings
from socialpeta_downloader.core.protocols import IEngineContext

class DeduplicationService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    # hàm đã hoạt động rồi đừng động vào
    def _init_image_md5_cache(self):
        """
        Quét thư mục tải xuống để tìm hình ảnh đã lưu và tính toán mã MD5 của chúng.
        """
        if not self.context:
            return
            
        path_to_ad_id = {}
        csv_path = self.context.csv_path
        
        # 1. Query SQLite database first for active download history paths
        db_path = self.context.get_db_path()
        if os.path.exists(db_path):
            import sqlite3
            try:
                conn = sqlite3.connect(db_path, timeout=10.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                cursor = conn.cursor()
                cursor.execute("SELECT ad_id, saved_path FROM download_history WHERE saved_path IS NOT NULL AND saved_path != ''")
                for ad_id, saved_path in cursor.fetchall():
                    resolved_path = self.context.utils_service.resolve_saved_path(saved_path)
                    norm_path = os.path.normpath(resolved_path)
                    path_to_ad_id[norm_path] = ad_id
                conn.close()
            except Exception as e:
                import traceback
                self.context.log("error", f"[-] Loi doc SQLite trong init image md5 cache: {e}\n{traceback.format_exc()}")
                
        # 2. Fallback to CSV if path_to_ad_id is empty
        if not path_to_ad_id and os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        saved_path = r.get("saved_path")
                        ad_id = r.get("ad_id")
                        if saved_path and ad_id:
                            resolved_path = self.context.utils_service.resolve_saved_path(saved_path)
                            norm_path = os.path.normpath(resolved_path)
                            path_to_ad_id[norm_path] = ad_id
            except Exception as e:
                import traceback
                self.context.log("error", f"[-] Loi doc csv trong init image md5 cache: {e}\n{traceback.format_exc()}")

        download_dir = self.context.download_dir
        if not os.path.exists(download_dir):
            return
        try:
            for filename in os.listdir(download_dir):
                filepath = os.path.join(download_dir, filename)
                if os.path.isfile(filepath):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                        md5 = self._get_file_md5(filepath)
                        if md5:
                            norm_filepath = os.path.normpath(filepath)
                            ad_id = path_to_ad_id.get(norm_filepath) or "unknown_existing"
                            self.context.image_md5_cache[md5] = ad_id
        except Exception as e:
            import traceback
            self.context.log("error", f"[-] Loi khoi tao image md5 cache: {e}\n{traceback.format_exc()}")
    # hàm đã hoạt động rồi đừng động vào
    def _get_file_md5(self, filepath: str) -> Optional[str]:
        """
        Tính toán mã MD5 của một tệp tin.
        """
        try:
            hasher = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Error calculating file MD5 for {filepath}: {e}\n{traceback.format_exc()}")
            return None

    # hàm đã hoạt động rồi đừng động vào
    def get_video_duration(self, file_path: str) -> float:
        """
        Sử dụng ffprobe để lấy thời lượng (duration) của video.
        """
        try:
            cmd = [
                settings.FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", file_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=10)
            return float(res.stdout.strip())
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Loi lay duration tu ffprobe: {e}\n{traceback.format_exc()}")
            else:
                print(f"[-] Loi lay duration tu ffprobe: {e}\n{traceback.format_exc()}")
            return -1.0

    # hàm đã hoạt động rồi đừng động vào
    def get_audio_pcm_md5(self, file_path: str) -> Optional[str]:
        """
        Trích xuất luồng âm thanh dạng PCM 16kHz mono từ video bằng ffmpeg và tính mã MD5 của nó.
        """
        try:
            cmd = [
                settings.FFMPEG_PATH, "-y", "-i", file_path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
            if res.returncode != 0 or not res.stdout:
                return None
            return hashlib.md5(res.stdout).hexdigest()
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Loi lay audio PCM md5 tu ffmpeg: {e}\n{traceback.format_exc()}")
            return None

    # hàm đã hoạt động rồi đừng động vào
    def get_frame_hash_and_brightness(self, file_path: str, timestamp: float) -> Optional[Tuple[int, float]]:
        """
        Trích xuất một khung hình tại thời điểm timestamp, giảm độ phân giải xuống 9x8 grayscale,
        tính toán mã dHash trực quan và độ sáng trung bình của khung hình đó.
        """
        try:
            cmd = [
                settings.FFMPEG_PATH, "-y", "-ss", f"{timestamp:.3f}", "-i", file_path,
                "-vframes", "1", "-vf", "scale=9x8,format=gray", "-f", "rawvideo", "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15)
            if res.returncode != 0 or len(res.stdout) != 72:
                return None
            
            pixels = list(res.stdout)
            brightness = sum(pixels) / 72.0
            
            hash_val = 0
            for row in range(8):
                for col in range(8):
                    idx = row * 9 + col
                    if pixels[idx] > pixels[idx + 1]:
                        hash_val |= (1 << (row * 8 + col))
            return hash_val, brightness
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Loi lay frame hash/brightness: {e}\n{traceback.format_exc()}")
            return None

    # hàm đã hoạt động rồi đừng động vào
    def get_temp_json_path(self, ad_id: str) -> Optional[str]:
        """
        Tìm kiếm đường dẫn tệp JSON tạm thời của quảng cáo dựa trên ad_id trong các thư mục tab tạm.
        """
        if not self.context or not os.path.exists(self.context.temp_queue_dir):
            return None
        try:
            subdirs = [d for d in os.listdir(self.context.temp_queue_dir) if d.startswith("tab") or d == "api"]
            for subdir in subdirs:
                fpath = os.path.join(self.context.temp_queue_dir, subdir, f"{ad_id}.json")
                if os.path.exists(fpath):
                    return fpath
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Error listing/searching temp queue dir: {e}\n{traceback.format_exc()}")
        return None

    # hàm đã hoạt động rồi đừng động vào
    def check_duplicate(self, new_file: str) -> Tuple[bool, str, str]:
        """
        Thực hiện đối khớp lọc trùng video qua 3 lớp (Thời lượng, MD5 âm thanh PCM, mã dHash trực quan).
        """
        if not self.context:
            return False, "", "Context missing"
            
        new_dur = self.get_video_duration(new_file)
        if new_dur <= 0:
            return False, "", "ffprobe failed"
            
        import sqlite3
        saved_items = []
        db_path = self.context.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM download_history WHERE saved_path IS NOT NULL AND saved_path != ''")
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            for r in rows:
                item = dict(zip(cols, r))
                saved_path = item["saved_path"]
                resolved_path = self.context.utils_service.resolve_saved_path(saved_path)
                if resolved_path and os.path.exists(resolved_path):
                    item["saved_path"] = resolved_path
                    dur_val = item.get("duration")
                    try:
                        item["duration"] = float(dur_val) if dur_val else -1.0
                    except ValueError:
                        item["duration"] = -1.0
                    saved_items.append(item)
        except Exception as e:
            import traceback
            self.context.log("error", f"[-] Loi doc SQLite trong check_duplicate: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
                
        candidates = []
        for item in saved_items:
            existing_path = item["saved_path"]
            ext_dur = item.get("duration")
            if ext_dur is None or ext_dur == "":
                ext_dur = -1.0
                
            if ext_dur <= 0:
                ext_dur = self.get_video_duration(existing_path)
                if ext_dur > 0:
                    item["duration"] = ext_dur
                    self.context.session_service.append_to_csv(item)
                    
            if ext_dur > 0 and abs(new_dur - ext_dur) > 0.05:
                is_integer_like = (ext_dur == int(ext_dur))
                if is_integer_like and abs(new_dur - ext_dur) <= 1.5:
                    actual_dur = self.get_video_duration(existing_path)
                    if actual_dur > 0:
                        ext_dur = actual_dur
                        item["duration"] = ext_dur
                        self.context.session_service.append_to_csv(item)
                        
            if ext_dur > 0 and abs(new_dur - ext_dur) <= 0.05:
                candidates.append((item, existing_path))
                
        if not candidates:
            return False, "", "Layer 1: No duration matches"
            
        new_audio_md5 = self.get_audio_pcm_md5(new_file)
        if new_audio_md5:
            for item, path in candidates:
                ext_audio_md5 = item.get("audio_pcm_md5")
                if not ext_audio_md5:
                    orig_item = self.context.utils_service.db_get_item(item["ad_id"])
                    if orig_item:
                        ext_audio_md5 = orig_item.get("audio_pcm_md5")
                if not ext_audio_md5:
                    ext_audio_md5 = self.get_audio_pcm_md5(path)
                    if ext_audio_md5:
                        orig_item = self.context.utils_service.db_get_item(item["ad_id"])
                        if not orig_item:
                            orig_item = item.copy()
                        orig_item["audio_pcm_md5"] = ext_audio_md5
                        self.context.utils_service._write_item_file(orig_item.get("fpath", ""), orig_item)
                if ext_audio_md5 and ext_audio_md5 == new_audio_md5:
                    return True, item["ad_id"], "Layer 2: Audio PCM MD5 matches"
                    
        new_ad_id = os.path.splitext(os.path.basename(new_file))[0]
        new_item_data = self.context.utils_service.db_get_item(new_ad_id)
        new_frames = None
        if new_item_data:
            new_frames = new_item_data.get("dhash_cache")
                
        if not isinstance(new_frames, list) or len(new_frames) != 5:
            new_frames = None

        if not new_frames:
            timestamps = [new_dur * p for p in [0.10, 0.30, 0.50, 0.70, 0.90]]
            new_frames = []
            for t in timestamps:
                res = self.get_frame_hash_and_brightness(new_file, t)
                new_frames.append(res)
            if new_item_data is not None:
                try:
                    new_item_data["dhash_cache"] = new_frames
                    self.context.utils_service._write_item_file(new_item_data.get("fpath", ""), new_item_data)
                except Exception as e:
                    import traceback
                    if self.context:
                        self.context.log("error", f"[-] Error writing dhash cache to item state: {e}\n{traceback.format_exc()}")
            
        for item, path in candidates:
            ext_frames = None
            orig_item = self.context.utils_service.db_get_item(item["ad_id"])
            if orig_item:
                ext_frames = orig_item.get("dhash_cache")
                    
            if not isinstance(ext_frames, list) or len(ext_frames) != 5:
                ext_frames = None
                
            if not ext_frames:
                timestamps = [new_dur * p for p in [0.10, 0.30, 0.50, 0.70, 0.90]]
                ext_frames = []
                for t in timestamps:
                    res = self.get_frame_hash_and_brightness(path, t)
                    ext_frames.append(res)
                if orig_item is None:
                    orig_item = item.copy()
                try:
                    orig_item["dhash_cache"] = ext_frames
                    self.context.utils_service._write_item_file(orig_item.get("fpath", ""), orig_item)
                except Exception as e:
                    import traceback
                    if self.context:
                        self.context.log("error", f"[-] Error writing dhash cache to item state: {e}\n{traceback.format_exc()}")
                
            matches = 0
            valid_frames = 0
            if ext_frames:
                for f_new, f_ext in zip(new_frames, ext_frames):
                    if f_new is None or f_ext is None:
                        continue
                    valid_frames += 1
                    h_new, b_new = f_new
                    h_ext, b_ext = f_ext
                    
                    hamming_dist = bin(h_new ^ h_ext).count('1')
                    bright_diff = abs(b_new - b_ext) / 255.0
                    
                    if hamming_dist <= 13 and bright_diff <= 0.10:
                        matches += 1
                        
            if valid_frames > 0 and (matches / valid_frames) >= 0.8:
                return True, item["ad_id"], f"Layer 3: dHash visual match ({matches}/{valid_frames} frames)"
                
        return False, "", "Checked all layers, no duplicate found"
