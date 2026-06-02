import sqlite3
import os

db_path = r"data\db.sqlite3"
if not os.path.exists(db_path):
    print("Database does not exist at:", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Tables:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

print("\n--- ad_metadata count ---")
cursor.execute("SELECT COUNT(*) FROM ad_metadata;")
print("Count:", cursor.fetchone()[0])
cursor.execute("SELECT status, COUNT(*) FROM ad_metadata GROUP BY status;")
print("Statuses:", cursor.fetchall())

print("\n--- download_history count ---")
cursor.execute("SELECT COUNT(*) FROM download_history;")
print("Count:", cursor.fetchone()[0])

print("\n--- download_history sample (last 5) ---")
cursor.execute("SELECT ad_id, app_name, platform, area, media_type, file_size, download_time FROM download_history ORDER BY download_time DESC LIMIT 5;")
for r in cursor.fetchall():
    print(r)

print("\n--- duplicate_audit count ---")
cursor.execute("SELECT COUNT(*) FROM duplicate_audit;")
print("Count:", cursor.fetchone()[0])

conn.close()
