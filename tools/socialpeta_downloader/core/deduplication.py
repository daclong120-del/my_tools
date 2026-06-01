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
from typing import TYPE_CHECKING, Optional

class DedupMixin:
    csv_path: str
    download_dir: str
    image_md5_cache: dict
    metadata_lock: threading.RLock
    temp_queue_dir: str

    if TYPE_CHECKING:
        def append_to_csv(self, item: dict) -> None: ...
        def _write_item_file(self, fpath: str, item: dict) -> None: ...

    def _init_image_md5_cache(self):
        """
        Scan download folder for saved images and calculate MD5.
        """
        path_to_ad_id = {}
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        saved_path = r.get("saved_path")
                        ad_id = r.get("ad_id")
                        if saved_path and ad_id:
                            norm_path = os.path.normpath(saved_path)
                            path_to_ad_id[norm_path] = ad_id
            except Exception as e:
                print(f"[-] Loi doc csv trong init image md5 cache: {e}")

        if not os.path.exists(self.download_dir):
            return
        try:
            for filename in os.listdir(self.download_dir):
                filepath = os.path.join(self.download_dir, filename)
                if os.path.isfile(filepath):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                        md5 = self._get_file_md5(filepath)
                        if md5:
                            norm_filepath = os.path.normpath(filepath)
                            ad_id = path_to_ad_id.get(norm_filepath) or "unknown_existing"
                            self.image_md5_cache[md5] = ad_id
        except Exception as e:
            print(f"[-] Loi khoi tao image md5 cache: {e}")

    def _get_file_md5(self, filepath: str) -> Optional[str]:
        try:
            hasher = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def get_video_duration(self, file_path: str) -> float:
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", file_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=10)
            return float(res.stdout.strip())
        except Exception as e:
            print(f"[-] Loi lay duration tu ffprobe: {e}")
            return -1.0

    def get_audio_pcm_md5(self, file_path: str) -> Optional[str]:
        try:
            cmd = [
                "ffmpeg", "-y", "-i", file_path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
            if res.returncode != 0 or not res.stdout:
                return None
            return hashlib.md5(res.stdout).hexdigest()
        except Exception:
            return None

    def get_frame_hash_and_brightness(self, file_path: str, timestamp: float) -> Optional[tuple[int, float]]:
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", file_path,
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
        except Exception:
            return None

    def get_temp_json_path(self, ad_id: str) -> Optional[str]:
        if not os.path.exists(self.temp_queue_dir):
            return None
        try:
            subdirs = [d for d in os.listdir(self.temp_queue_dir) if d.startswith("tab") or d == "api"]
            for subdir in subdirs:
                fpath = os.path.join(self.temp_queue_dir, subdir, f"{ad_id}.json")
                if os.path.exists(fpath):
                    return fpath
        except Exception:
            pass
        return None

    def check_duplicate(self, new_file: str) -> tuple[bool, str, str]:
        """
        3-layer deduplication matching.
        """
        new_dur = self.get_video_duration(new_file)
        if new_dur <= 0:
            return False, "", "ffprobe failed"
            
        saved_items = []
        if os.path.exists(self.csv_path):
            try:
                with self.metadata_lock:
                    with open(self.csv_path, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            saved_path = r.get("saved_path")
                            if saved_path and os.path.exists(saved_path):
                                dur_val = r.get("duration")
                                try:
                                    r["duration"] = float(dur_val) if dur_val else -1.0
                                except ValueError:
                                    r["duration"] = -1.0
                                saved_items.append(r)
            except Exception as e:
                print(f"[-] Loi doc csv trong check_duplicate: {e}")
                
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
                    self.append_to_csv(item)
                    
            if ext_dur > 0 and abs(new_dur - ext_dur) > 0.05:
                is_integer_like = (ext_dur == int(ext_dur))
                if is_integer_like and abs(new_dur - ext_dur) <= 1.5:
                    actual_dur = self.get_video_duration(existing_path)
                    if actual_dur > 0:
                        ext_dur = actual_dur
                        item["duration"] = ext_dur
                        self.append_to_csv(item)
                        
            if ext_dur > 0 and abs(new_dur - ext_dur) <= 0.05:
                candidates.append((item, existing_path))
                
        if not candidates:
            return False, "", "Layer 1: No duration matches"
            
        new_audio_md5 = self.get_audio_pcm_md5(new_file)
        if new_audio_md5:
            for item, path in candidates:
                ext_audio_md5 = item.get("audio_pcm_md5")
                if not ext_audio_md5:
                    item_fpath = self.get_temp_json_path(item["ad_id"])
                    if item_fpath:
                        try:
                            with open(item_fpath, 'r', encoding='utf-8') as f:
                                orig_item = json.load(f)
                            ext_audio_md5 = orig_item.get("audio_pcm_md5")
                        except Exception:
                            pass
                if not ext_audio_md5:
                    ext_audio_md5 = self.get_audio_pcm_md5(path)
                    if ext_audio_md5:
                        item_fpath = self.get_temp_json_path(item["ad_id"])
                        if item_fpath:
                            try:
                                with open(item_fpath, 'r', encoding='utf-8') as f:
                                    orig_item = json.load(f)
                                orig_item["audio_pcm_md5"] = ext_audio_md5
                                self._write_item_file(item_fpath, orig_item)
                            except Exception:
                                pass
                if ext_audio_md5 and ext_audio_md5 == new_audio_md5:
                    return True, item["ad_id"], "Layer 2: Audio PCM MD5 matches"
                    
        new_ad_id = os.path.splitext(os.path.basename(new_file))[0]
        new_fpath = self.get_temp_json_path(new_ad_id)
        new_frames = None
        new_item_data = None
        if new_fpath:
            try:
                with open(new_fpath, 'r', encoding='utf-8') as f:
                    new_item_data = json.load(f)
                new_frames = new_item_data.get("dhash_cache")
            except Exception:
                pass
                
        if not isinstance(new_frames, list) or len(new_frames) != 5:
            new_frames = None

        if not new_frames:
            timestamps = [new_dur * p for p in [0.10, 0.30, 0.50, 0.70, 0.90]]
            new_frames = []
            for t in timestamps:
                res = self.get_frame_hash_and_brightness(new_file, t)
                new_frames.append(res)
            if new_item_data is not None and new_fpath:
                try:
                    new_item_data["dhash_cache"] = new_frames
                    self._write_item_file(new_fpath, new_item_data)
                except Exception:
                    pass
            
        for item, path in candidates:
            ext_frames = None
            item_fpath = self.get_temp_json_path(item["ad_id"])
            orig_item = None
            if item_fpath:
                try:
                    with open(item_fpath, 'r', encoding='utf-8') as f:
                        orig_item = json.load(f)
                    ext_frames = orig_item.get("dhash_cache")
                except Exception:
                    pass
                    
            if not isinstance(ext_frames, list) or len(ext_frames) != 5:
                ext_frames = None
                
            if not ext_frames:
                timestamps = [new_dur * p for p in [0.10, 0.30, 0.50, 0.70, 0.90]]
                ext_frames = []
                for t in timestamps:
                    res = self.get_frame_hash_and_brightness(path, t)
                    ext_frames.append(res)
                if item_fpath:
                    if orig_item is None:
                        orig_item = item.copy()
                    try:
                        orig_item["dhash_cache"] = ext_frames
                        self._write_item_file(item_fpath, orig_item)
                    except Exception:
                        pass
                
            matches = 0
            valid_frames = 0
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
