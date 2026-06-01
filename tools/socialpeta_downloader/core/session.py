# tools/socialpeta_downloader/core/session.py
"""
Responsibility: CSV operations, duplicate audit log, and session restoration.
"""

import os
import csv
import json
import time
import queue
import threading
from datetime import datetime
from typing import TYPE_CHECKING


class SessionMixin:
    metadata_lock: threading.RLock
    csv_path: str
    audit_csv_path: str
    temp_queue_dir: str
    temp_download_dir: str
    item_status_cache: dict
    ad_id_to_status: dict
    stats_lock: threading.Lock
    stats: dict
    pending_downloads: queue.PriorityQueue
    filter_queue: queue.Queue

    if TYPE_CHECKING:
        def _write_item_file(self, fpath: str, item: dict) -> None: ...


    def append_to_csv(self, item: dict):
        """
        Ghi/cap nhat thong tin vao download_info.csv (Thread-safe)
        """
        if not item.get("saved_path"):
            print(f"[WARN] Record ghi CSV nhung saved_path trong: ad_id={item.get('ad_id')}")
        with self.metadata_lock:
            file_exists = os.path.exists(self.csv_path)
            rows = []
            updated = False
            fieldnames = [
                "ad_id", "video_name", "media_type", "video_url", "youtube_url", 
                "duration", "impression", "heat", "platform", "download_time", 
                "publisher", "app_name", "area", "copywriting_language", "title", 
                "body", "deployment_time", "saved_path", "file_size"
            ]
            
            if file_exists:
                try:
                    with open(self.csv_path, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            if r.get("ad_id") == item["ad_id"]:
                                r.update({
                                    "video_name": item.get("video_name", r.get("video_name", "")),
                                    "media_type": item.get("media_type", r.get("media_type", "")),
                                    "video_url": item.get("video_url", r.get("video_url", "")),
                                    "youtube_url": item.get("youtube_url", r.get("youtube_url", "")),
                                    "duration": str(item.get("duration", r.get("duration", ""))),
                                    "impression": item.get("impression", r.get("impression", "")),
                                    "heat": item.get("heat", r.get("heat", "")),
                                    "platform": item.get("platform", r.get("platform", "")),
                                    "download_time": item.get("download_time", r.get("download_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
                                    "publisher": item.get("publisher", r.get("publisher", "")),
                                    "app_name": item.get("app_name", r.get("app_name", "")),
                                    "area": item.get("area", r.get("area", "")),
                                    "copywriting_language": item.get("copywriting_language", r.get("copywriting_language", "")),
                                    "title": item.get("title", r.get("title", "")),
                                    "body": item.get("body", r.get("body", "")),
                                    "deployment_time": item.get("deployment_time", r.get("deployment_time", "")),
                                    "saved_path": item.get("saved_path", r.get("saved_path", "")),
                                    "file_size": str(item.get("file_size", r.get("file_size", "0")))
                                })
                                updated = True
                            row_dict = {k: r.get(k, "") for k in fieldnames}
                            rows.append(row_dict)
                except Exception as e:
                    print(f"[-] Loi doc download_info.csv: {e}")
            
            if not updated:
                rows.append({
                    "ad_id": item["ad_id"],
                    "video_name": item.get("video_name", ""),
                    "media_type": item.get("media_type", "video"),
                    "video_url": item.get("video_url", ""),
                    "youtube_url": item.get("youtube_url", ""),
                    "duration": str(item.get("duration", "")),
                    "impression": item.get("impression", ""),
                    "heat": item.get("heat", ""),
                    "platform": item.get("platform", ""),
                    "download_time": item.get("download_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "publisher": item.get("publisher", ""),
                    "app_name": item.get("app_name", ""),
                    "area": item.get("area", ""),
                    "copywriting_language": item.get("copywriting_language", ""),
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "deployment_time": item.get("deployment_time", ""),
                    "saved_path": item.get("saved_path", ""),
                    "file_size": str(item.get("file_size", "0"))
                })
                
            try:
                with open(self.csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            except Exception as e:
                print(f"[-] Loi ghi download_info.csv: {e}")

    def append_to_audit_csv(self, ad_id: str, app_name: str, dup_ad_id: str, reason: str):
        with self.metadata_lock:
            file_exists = os.path.exists(self.audit_csv_path)
            fieldnames = ["timestamp", "ad_id", "app_name", "duplicate_ad_id", "reason"]
            try:
                with open(self.audit_csv_path, 'a', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "ad_id": ad_id,
                        "app_name": app_name,
                        "duplicate_ad_id": dup_ad_id,
                        "reason": reason
                    })
            except Exception as e:
                print(f"[-] Loi ghi duplicate_audit.csv: {e}")

    def restore_session(self):
        """
        UC-06a & UC-06b / UC-T02: Phuc hoi phien lam viec cu
        """
        print("[*] Dang phuc hoi phien lam viec cu...")
        restored_filter_count = 0
        reset_count = 0
        
        if not os.path.exists(self.temp_queue_dir):
            return
            
        try:
            subdirs = [d for d in os.listdir(self.temp_queue_dir) if d.startswith("tab") or d == "api"]
            for subdir in subdirs:
                subdir_path = os.path.join(self.temp_queue_dir, subdir)
                if os.path.isdir(subdir_path):
                    for fname in os.listdir(subdir_path):
                        if fname.endswith(".json") and not fname.endswith(".tmp"):
                            fpath = os.path.join(subdir_path, fname)
                            try:
                                with open(fpath, 'r', encoding='utf-8') as f:
                                    item = json.load(f)
                                status = item.get("status", "pending")
                                ad_id = item.get("ad_id")
                                
                                self.item_status_cache[fpath] = status
                                if ad_id:
                                    self.ad_id_to_status[ad_id] = status
                                with self.stats_lock:
                                    self.stats["total_sniffed"] += 1
                                    if status in self.stats:
                                        self.stats[status] += 1
                                
                                if status == "downloading":
                                    temp_file = os.path.join(self.temp_download_dir, f"{ad_id}.tmp")
                                    if not os.path.exists(temp_file):
                                        item["status"] = "pending"
                                        self._write_item_file(fpath, item)
                                        reset_count += 1
                                        try:
                                            mtime = os.path.getmtime(fpath)
                                        except Exception:
                                            mtime = time.time()
                                        self.pending_downloads.put((mtime, fpath))
                                        
                                elif status == "downloaded":
                                    temp_path = item.get("saved_path")
                                    if not temp_path or not os.path.exists(temp_path):
                                        temp_path = os.path.join(self.temp_download_dir, f"{ad_id}.mp4")
                                    if os.path.exists(temp_path):
                                        item["saved_path"] = temp_path
                                        self.filter_queue.put((fpath, item))
                                        restored_filter_count += 1
                                    else:
                                        item["status"] = "pending"
                                        self._write_item_file(fpath, item)
                                        reset_count += 1
                                        try:
                                            mtime = os.path.getmtime(fpath)
                                        except Exception:
                                            mtime = time.time()
                                        self.pending_downloads.put((mtime, fpath))
                                elif status == "pending":
                                    try:
                                        mtime = os.path.getmtime(fpath)
                                    except Exception:
                                        mtime = time.time()
                                    self.pending_downloads.put((mtime, fpath))
                            except Exception:
                                pass
        except Exception as e:
            print(f"[-] Error restoring session: {e}")
            
        print(f"[+] Phuc hoi phien: Reset {reset_count} item ve pending, xep hang {restored_filter_count} item cho dedup.")
