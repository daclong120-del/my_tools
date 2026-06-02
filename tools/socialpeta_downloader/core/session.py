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
from typing import Optional
from socialpeta_downloader.core.protocols import IEngineContext
from socialpeta_downloader.config import settings

class SessionService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def init_db(self):
        if not self.context:
            return
        import sqlite3
        db_path = self.context.get_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS download_history (
                    ad_id TEXT PRIMARY KEY,
                    video_name TEXT,
                    media_type TEXT,
                    video_url TEXT,
                    youtube_url TEXT,
                    duration TEXT,
                    impression TEXT,
                    heat TEXT,
                    platform TEXT,
                    download_time TEXT,
                    publisher TEXT,
                    app_name TEXT,
                    area TEXT,
                    copywriting_language TEXT,
                    title TEXT,
                    body TEXT,
                    deployment_time TEXT,
                    saved_path TEXT,
                    file_size TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS duplicate_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ad_id TEXT,
                    app_name TEXT,
                    duplicate_ad_id TEXT,
                    reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ad_metadata (
                    ad_id TEXT PRIMARY KEY,
                    fpath TEXT,
                    status TEXT,
                    item_json TEXT,
                    mtime REAL
                )
            """)
            conn.commit()
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Error initializing SQLite database: {e}\n{traceback.format_exc()}")
            else:
                print(f"[-] Error initializing SQLite database: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()

    def migrate_old_data(self, old_download_dir: Optional[str] = None):
        if not self.context:
            return
        import sqlite3
        db_path = self.context.get_db_path()
        
        # Determine old db/csv/audit path candidates to migrate from
        old_db_path = None
        old_csv_path = None
        old_audit_csv_path = None
        
        if old_download_dir:
            old_db_path = os.path.join(old_download_dir, "db.sqlite3")
            old_csv_path = os.path.join(old_download_dir, "download_info.csv")
            old_audit_csv_path = os.path.join(old_download_dir, "duplicate_audit.csv")
        else:
            # Fallback to the default application data directory db.sqlite3
            default_db_path = os.path.join(settings.DATA_DIR, "db.sqlite3")
            if os.path.exists(default_db_path) and os.path.abspath(default_db_path) != os.path.abspath(db_path):
                old_db_path = default_db_path
                
        # 1. Migrate old SQLite database to new SQLite database
        if old_db_path and os.path.exists(old_db_path) and os.path.abspath(old_db_path) != os.path.abspath(db_path):
            print(f"[*] Migrating old SQLite db {old_db_path} to {db_path}...")
            try:
                conn = sqlite3.connect(db_path, timeout=10.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                try:
                    conn.execute(f"ATTACH DATABASE '{old_db_path}' AS old_db")
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO download_history
                        SELECT * FROM old_db.download_history
                    """)
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO duplicate_audit (timestamp, ad_id, app_name, duplicate_ad_id, reason)
                        SELECT timestamp, ad_id, app_name, duplicate_ad_id, reason FROM old_db.duplicate_audit
                    """)
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO ad_metadata
                        SELECT * FROM old_db.ad_metadata
                    """)
                    
                    conn.commit()
                    print("[+] Merged old SQLite database records into new database.")
                except Exception as e:
                    import traceback
                    if self.context:
                        self.context.log("error", f"[-] Error attaching/merging old SQLite db: {e}\n{traceback.format_exc()}")
                finally:
                    try:
                        conn.execute("DETACH DATABASE old_db")
                    except Exception:
                        pass
                    conn.close()
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Error opening connection for old SQLite migration: {e}\n{traceback.format_exc()}")

        # 2. Migrate download_info.csv
        csv_candidates = []
        if old_csv_path and os.path.exists(old_csv_path):
            csv_candidates.append(old_csv_path)
        current_csv = self.context.csv_path
        if os.path.exists(current_csv) and current_csv not in csv_candidates:
            csv_candidates.append(current_csv)
            
        for csv_path in csv_candidates:
            print(f"[*] Migrating {csv_path} to SQLite...")
            try:
                rows_to_insert = []
                with open(csv_path, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        ad_id = r.get("ad_id")
                        if not ad_id:
                            continue
                        rows_to_insert.append((
                            ad_id,
                            r.get("video_name", ""),
                            r.get("media_type", "video"),
                            r.get("video_url", ""),
                            r.get("youtube_url", ""),
                            r.get("duration", ""),
                            r.get("impression", ""),
                            r.get("heat", ""),
                            r.get("platform", ""),
                            r.get("download_time", ""),
                            r.get("publisher", ""),
                            r.get("app_name", ""),
                            r.get("area", ""),
                            r.get("copywriting_language", ""),
                            r.get("title", ""),
                            r.get("body", ""),
                            r.get("deployment_time", ""),
                            r.get("saved_path", ""),
                            r.get("file_size", "0")
                        ))
                
                if rows_to_insert:
                    conn = sqlite3.connect(db_path, timeout=10.0)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=5000;")
                    try:
                        cursor = conn.cursor()
                        cursor.executemany("""
                            INSERT OR IGNORE INTO download_history (
                                ad_id, video_name, media_type, video_url, youtube_url,
                                duration, impression, heat, platform, download_time,
                                publisher, app_name, area, copywriting_language, title,
                                body, deployment_time, saved_path, file_size
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, rows_to_insert)
                        conn.commit()
                        print(f"[+] Migrated {len(rows_to_insert)} records to download_history.")
                    except Exception as e:
                        import traceback
                        if self.context:
                            self.context.log("error", f"[-] SQLite insertion error: {e}\n{traceback.format_exc()}")
                    finally:
                        conn.close()
                
                bak_path = csv_path + ".bak"
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(csv_path, bak_path)
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Error migrating csv to sqlite: {e}\n{traceback.format_exc()}")
                
        # 3. Migrate duplicate_audit.csv
        audit_csv_candidates = []
        if old_audit_csv_path and os.path.exists(old_audit_csv_path):
            audit_csv_candidates.append(old_audit_csv_path)
        current_audit_csv = self.context.audit_csv_path
        if os.path.exists(current_audit_csv) and current_audit_csv not in audit_csv_candidates:
            audit_csv_candidates.append(current_audit_csv)
            
        for audit_csv in audit_csv_candidates:
            print(f"[*] Migrating {audit_csv} to SQLite...")
            try:
                rows_to_insert = []
                with open(audit_csv, 'r', encoding='utf-8-sig', newline='', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        rows_to_insert.append((
                            r.get("timestamp", ""),
                            r.get("ad_id", ""),
                            r.get("app_name", ""),
                            r.get("duplicate_ad_id", ""),
                            r.get("reason", "")
                        ))
                if rows_to_insert:
                    conn = sqlite3.connect(db_path, timeout=10.0)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=5000;")
                    try:
                        cursor = conn.cursor()
                        cursor.executemany("""
                            INSERT INTO duplicate_audit (timestamp, ad_id, app_name, duplicate_ad_id, reason)
                            VALUES (?, ?, ?, ?, ?)
                        """, rows_to_insert)
                        conn.commit()
                        print(f"[+] Migrated {len(rows_to_insert)} records to duplicate_audit.")
                    except Exception as e:
                        import traceback
                        if self.context:
                            self.context.log("error", f"[-] SQLite insertion error for duplicate_audit: {e}\n{traceback.format_exc()}")
                    finally:
                        conn.close()
                
                bak_path = audit_csv + ".bak"
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(audit_csv, bak_path)
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Error migrating audit csv to sqlite: {e}\n{traceback.format_exc()}")
                
        # 4. Migrate local JSON files in .temp/
        temp_queue_dir = self.context.temp_queue_dir
        if os.path.exists(temp_queue_dir):
            print(f"[*] Migrating local JSON metadata files to SQLite...")
            try:
                conn = sqlite3.connect(db_path, timeout=10.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                cursor = conn.cursor()
                
                subdirs = [d for d in os.listdir(temp_queue_dir) if d.startswith("tab") or d == "api"]
                for subdir in subdirs:
                    subdir_path = os.path.join(temp_queue_dir, subdir)
                    if os.path.isdir(subdir_path):
                        for fname in os.listdir(subdir_path):
                            if fname.endswith(".json"):
                                fpath = os.path.join(subdir_path, fname)
                                try:
                                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                        item = json.load(f)
                                    ad_id = item.get("ad_id")
                                    status = item.get("status", "pending")
                                    mtime = os.path.getmtime(fpath)
                                    if ad_id:
                                        cursor.execute("""
                                            INSERT OR REPLACE INTO ad_metadata (ad_id, fpath, status, item_json, mtime)
                                            VALUES (?, ?, ?, ?, ?)
                                        """, (ad_id, fpath, status, json.dumps(item, ensure_ascii=False), mtime))
                                    bak_path = fpath + ".bak"
                                    if os.path.exists(bak_path):
                                        os.remove(bak_path)
                                    os.rename(fpath, bak_path)
                                except Exception as ex:
                                    import traceback
                                    if self.context:
                                        self.context.log("error", f"[-] Failed to migrate JSON file {fname}: {ex}\n{traceback.format_exc()}")
                conn.commit()
                conn.close()
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Error migrating temporary JSON files: {e}\n{traceback.format_exc()}")

        # Synchronize SQLite tables back to CSV files in the current workspace
        self.sync_db_to_csv()
        self.sync_audit_db_to_csv()

    def append_to_csv(self, item: dict):
        """
        Save or update in download_history table (thread-safe, WAL mode).
        """
        if not self.context:
            return
            
        if not item.get("saved_path"):
            print(f"[WARN] Record ghi CSV nhung saved_path trong: ad_id={item.get('ad_id')}")
        
        with self.context.history_lock:
            import sqlite3
            db_path = self.context.get_db_path()
            ad_id = item["ad_id"]
            
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM download_history WHERE ad_id = ?", (ad_id,))
                r = cursor.fetchone()
                row = None
                if r:
                    cols = [col[0] for col in cursor.description]
                    row = dict(zip(cols, r))
                    
                # Convert saved_path to relative path for database storage
                saved_path = item.get("saved_path") or (row.get("saved_path") if row else "")
                rel_saved_path = self.context.utils_service.get_relative_path(saved_path)
                
                merged = {
                    "ad_id": ad_id,
                    "video_name": item.get("video_name", row.get("video_name", "") if row else ""),
                    "media_type": item.get("media_type", row.get("media_type", "video") if row else "video"),
                    "video_url": item.get("video_url", row.get("video_url", "") if row else ""),
                    "youtube_url": item.get("youtube_url", row.get("youtube_url", "") if row else ""),
                    "duration": str(item.get("duration", row.get("duration", "") if row else "")),
                    "impression": item.get("impression", row.get("impression", "") if row else ""),
                    "heat": item.get("heat", row.get("heat", "") if row else ""),
                    "platform": item.get("platform", row.get("platform", "") if row else ""),
                    "download_time": item.get("download_time", row.get("download_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if row else datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "publisher": item.get("publisher", row.get("publisher", "") if row else ""),
                    "app_name": item.get("app_name", row.get("app_name", "") if row else ""),
                    "area": item.get("area", row.get("area", "") if row else ""),
                    "copywriting_language": item.get("copywriting_language", row.get("copywriting_language", "") if row else ""),
                    "title": item.get("title", row.get("title", "") if row else ""),
                    "body": item.get("body", row.get("body", "") if row else ""),
                    "deployment_time": item.get("deployment_time", row.get("deployment_time", "") if row else ""),
                    "saved_path": rel_saved_path,
                    "file_size": str(item.get("file_size", row.get("file_size", "0") if row else "0"))
                }
                
                cursor.execute("""
                    INSERT OR REPLACE INTO download_history (
                        ad_id, video_name, media_type, video_url, youtube_url,
                        duration, impression, heat, platform, download_time,
                        publisher, app_name, area, copywriting_language, title,
                        body, deployment_time, saved_path, file_size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    merged["ad_id"], merged["video_name"], merged["media_type"], merged["video_url"], merged["youtube_url"],
                    merged["duration"], merged["impression"], merged["heat"], merged["platform"], merged["download_time"],
                    merged["publisher"], merged["app_name"], merged["area"], merged["copywriting_language"], merged["title"],
                    merged["body"], merged["deployment_time"], merged["saved_path"], merged["file_size"]
                ))
                conn.commit()
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Loi ghi SQLite download_history: {e}\n{traceback.format_exc()}")
            finally:
                conn.close()
                
            # Sync SQLite history to CSV file under lock
            self.sync_db_to_csv()

    def append_to_audit_csv(self, ad_id: str, app_name: str, dup_ad_id: str, reason: str):
        if not self.context:
            return
            
        with self.context.history_lock:
            import sqlite3
            db_path = self.context.get_db_path()
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO duplicate_audit (timestamp, ad_id, app_name, duplicate_ad_id, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ad_id,
                    app_name,
                    dup_ad_id,
                    reason
                ))
                conn.commit()
            except Exception as e:
                import traceback
                if self.context:
                    self.context.log("error", f"[-] Loi ghi SQLite duplicate_audit: {e}\n{traceback.format_exc()}")
            finally:
                conn.close()
                
            # Sync duplicate audit to CSV under lock
            self.sync_audit_db_to_csv()

    def sync_db_to_csv(self):
        """
        Export all records from SQLite download_history to download_info.csv inside the active workspace.
        Uses UTF-8-sig encoding and thread-safe locking.
        """
        if not self.context:
            return
            
        with self.context.history_lock:
            csv_path = self.context.csv_path
            db_path = self.context.get_db_path()
            if not os.path.exists(db_path):
                return
                
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ad_id, video_name, media_type, video_url, youtube_url,
                           duration, impression, heat, platform, download_time,
                           publisher, app_name, area, copywriting_language, title,
                           body, deployment_time, saved_path, file_size
                    FROM download_history
                """)
                rows = cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=cols)
                    writer.writeheader()
                    for r in rows:
                        row_dict = dict(zip(cols, r))
                        writer.writerow(row_dict)
                print(f"[+] Synchronized {len(rows)} records from SQLite to {csv_path}")
            except Exception as e:
                import traceback
                self.context.log("error", f"[-] Error syncing database to CSV: {e}\n{traceback.format_exc()}")
            finally:
                conn.close()

    def sync_audit_db_to_csv(self):
        """
        Export all records from SQLite duplicate_audit to duplicate_audit.csv inside the active workspace.
        Uses UTF-8-sig encoding and thread-safe locking.
        """
        if not self.context:
            return
            
        with self.context.history_lock:
            csv_path = self.context.audit_csv_path
            db_path = self.context.get_db_path()
            if not os.path.exists(db_path):
                return
                
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, ad_id, app_name, duplicate_ad_id, reason
                    FROM duplicate_audit
                """)
                rows = cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=cols)
                    writer.writeheader()
                    for r in rows:
                        row_dict = dict(zip(cols, r))
                        writer.writerow(row_dict)
                print(f"[+] Synchronized {len(rows)} duplicate audit records from SQLite to {csv_path}")
            except Exception as e:
                import traceback
                self.context.log("error", f"[-] Error syncing duplicate audit database to CSV: {e}\n{traceback.format_exc()}")
            finally:
                conn.close()

    def restore_session(self):
        """
        UC-06a & UC-06b / UC-T02: Phuc hoi phien lam viec cu tu SQLite
        """
        if not self.context:
            return
        
        # Clear existing status maps and reset stats to 0 to avoid accumulation on restart
        self.context.item_status_cache.clear()
        self.context.ad_id_to_status.clear()
        with self.context.stats_lock:
            for k in list(self.context.stats.keys()):
                self.context.stats[k] = 0

        import sqlite3
        print("[*] Dang phuc hoi phien lam viec cu tu SQLite...")
        restored_filter_count = 0
        reset_count = 0
        
        db_path = self.context.get_db_path()
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT fpath, status, item_json, mtime FROM ad_metadata")
            rows = cursor.fetchall()
            for fpath, status, item_json, mtime_val in rows:
                try:
                    item = json.loads(item_json)
                    ad_id = item.get("ad_id")
                    
                    self.context.item_status_cache[fpath] = status
                    if ad_id:
                        self.context.ad_id_to_status[ad_id] = status
                    with self.context.stats_lock:
                        self.context.stats["total_sniffed"] += 1
                        if status in self.context.stats:
                            self.context.stats[status] += 1
                    
                    mtime = mtime_val if mtime_val else time.time()
                    
                    if status == "downloading":
                        temp_file = os.path.join(self.context.temp_download_dir, f"{ad_id}.tmp")
                        if not os.path.exists(temp_file):
                            item["status"] = "pending"
                            self.context.utils_service._write_item_file(fpath, item)
                            reset_count += 1
                            self.context.pending_downloads.put((mtime, fpath))
                            
                    elif status == "downloaded":
                        temp_path = item.get("saved_path")
                        if temp_path:
                            temp_path = self.context.utils_service.resolve_saved_path(temp_path)
                        if not temp_path or not os.path.exists(temp_path):
                            temp_path = os.path.join(self.context.temp_download_dir, f"{ad_id}.mp4")
                        if os.path.exists(temp_path):
                            item["saved_path"] = temp_path
                            self.context.filter_queue.put((fpath, item))
                            restored_filter_count += 1
                        else:
                            item["status"] = "pending"
                            self.context.utils_service._write_item_file(fpath, item)
                            reset_count += 1
                            self.context.pending_downloads.put((mtime, fpath))
                    elif status == "pending":
                        self.context.pending_downloads.put((mtime, fpath))
                except Exception as ex:
                    import traceback
                    if self.context:
                        self.context.log("error", f"[-] Restore error for item: {ex}\n{traceback.format_exc()}")
        except Exception as e:
            import traceback
            if self.context:
                self.context.log("error", f"[-] Error restoring session from SQLite: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
            
        print(f"[+] Phuc hoi phien: Reset {reset_count} item ve pending, xep hang {restored_filter_count} item cho dedup.")
