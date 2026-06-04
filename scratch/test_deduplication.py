import os
import sys
import shutil
import sqlite3
import hashlib
import subprocess
from typing import Optional, Tuple, Dict, Any

# Add tools to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from socialpeta_downloader.core.deduplication import DeduplicationService
from socialpeta_downloader.config import settings

def print_result(passed, text):
    if passed:
        print(f"✅ PASS - {text}")
    else:
        print(f"❌ FAIL - {text}")

# Create Mock Utils Service
class MockUtilsService:
    def __init__(self, context):
        self.context = context
        self.items_db = {}
        
    def resolve_saved_path(self, saved_path):
        return os.path.join(self.context.download_dir, os.path.basename(saved_path))
        
    def db_get_item(self, ad_id):
        return self.items_db.get(ad_id)
        
    def _write_item_file(self, fpath, item):
        ad_id = item.get("ad_id")
        if ad_id:
            self.items_db[ad_id] = item

class MockSessionService:
    def __init__(self, context):
        self.context = context
        
    def append_to_csv(self, item):
        pass

# Create Mock Engine Context
class MockEngineContext:
    def __init__(self, test_dir):
        self.download_dir = os.path.join(test_dir, "videos")
        self.temp_queue_dir = os.path.join(test_dir, "temp_queue")
        self.csv_path = os.path.join(test_dir, "download_info.csv")
        self.db_path = os.path.join(test_dir, "db.sqlite3")
        self.image_md5_cache = {}
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_queue_dir, exist_ok=True)
        
        self.utils_service = MockUtilsService(self)
        self.session_service = MockSessionService(self)
        
    def log(self, level, message):
        print(f"[{level.upper()}] {message}")
        
    def get_db_path(self):
        return self.db_path

def generate_test_media(test_dir):
    os.makedirs(os.path.join(test_dir, "videos"), exist_ok=True)
    video_path = os.path.join(test_dir, "test_video.mp4")
    image_path = os.path.join(test_dir, "videos", "test_image.png")
    
    # Generate 3-second test video with sine wave audio
    cmd_video = [
        "ffmpeg", "-y", 
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10", 
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=3", 
        "-pix_fmt", "yuv420p", "-acodec", "aac", video_path
    ]
    subprocess.run(cmd_video, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    # Generate test image
    cmd_image = [
        "ffmpeg", "-y", 
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", 
        "-vframes", "1", "-update", "1", image_path
    ]
    subprocess.run(cmd_image, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    return video_path, image_path

def init_db(db_path, ad_id, saved_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_history (
            ad_id TEXT PRIMARY KEY,
            saved_path TEXT,
            duration TEXT,
            audio_pcm_md5 TEXT,
            dhash_cache TEXT
        )
    """)
    cursor.execute(
        "INSERT OR REPLACE INTO download_history (ad_id, saved_path, duration) VALUES (?, ?, ?)",
        (ad_id, saved_path, "3.0")
    )
    conn.commit()
    conn.close()

def run_tests():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_env")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        video_path, image_path = generate_test_media(test_dir)
        print("[*] Generated test media successfully.")
    except Exception as e:
        print(f"❌ FAIL - Could not generate test media using ffmpeg: {e}")
        return
        
    context = MockEngineContext(test_dir)
    service = DeduplicationService(context)
    
    # 1. Test _get_file_md5
    md5 = service._get_file_md5(image_path)
    print_result(md5 is not None and len(md5) == 32, f"_get_file_md5 calculated successfully: {md5}")
    
    # 2. Test _init_image_md5_cache
    init_db(context.db_path, "img_ad_123", "test_image.png")
    service._init_image_md5_cache()
    cached_ad_id = context.image_md5_cache.get(md5)
    print_result(cached_ad_id == "img_ad_123", f"_init_image_md5_cache cached image MD5 mapped to ad_id '{cached_ad_id}'")
    
    # 3. Test get_video_duration
    dur = service.get_video_duration(video_path)
    print_result(abs(dur - 3.0) < 0.1, f"get_video_duration returned duration: {dur}s (Expected ~3.0s)")
    
    # 4. Test get_audio_pcm_md5
    audio_md5 = service.get_audio_pcm_md5(video_path)
    print_result(audio_md5 is not None and len(audio_md5) == 32, f"get_audio_pcm_md5 calculated: {audio_md5}")
    
    # 5. Test get_frame_hash_and_brightness
    res = service.get_frame_hash_and_brightness(video_path, 1.5)
    print_result(res is not None and isinstance(res, tuple) and len(res) == 2, f"get_frame_hash_and_brightness at 1.5s returned: {res}")
    
    # 6. Test get_temp_json_path
    ad_id = "test_ad_456"
    tab_dir = os.path.join(context.temp_queue_dir, "tab0")
    os.makedirs(tab_dir, exist_ok=True)
    temp_json_file = os.path.join(tab_dir, f"{ad_id}.json")
    with open(temp_json_file, 'w') as f:
        f.write("{}")
    temp_path = service.get_temp_json_path(ad_id)
    print_result(temp_path == temp_json_file, f"get_temp_json_path found temp JSON file: {temp_path}")
    
    # 7. Test check_duplicate (Exact same file)
    # Register existing video in SQLite db
    # Set saved_path as relative or absolute, our mock resolve will handle it
    # First, let's copy the video to download folder
    dest_video_path = os.path.join(context.download_dir, "existing_video.mp4")
    shutil.copy(video_path, dest_video_path)
    
    init_db(context.db_path, "existing_ad", "existing_video.mp4")
    
    # Run duplicate check on the same video path
    is_dup, dup_ad_id, dup_msg = service.check_duplicate(dest_video_path)
    print_result(is_dup and dup_ad_id == "existing_ad", f"check_duplicate correctly detected duplicate. ID: {dup_ad_id}, Msg: {dup_msg}")

    # 8. Test check_duplicate (Layer 3: Same video frames, different audio)
    # Generate another video with different audio frequency
    video_path_diff_audio = os.path.join(test_dir, "test_video_diff_audio.mp4")
    cmd_video_diff = [
        "ffmpeg", "-y", 
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10", 
        "-f", "lavfi", "-i", "sine=frequency=2000:duration=3", 
        "-pix_fmt", "yuv420p", "-acodec", "aac", video_path_diff_audio
    ]
    subprocess.run(cmd_video_diff, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    is_dup3, dup_ad_id3, dup_msg3 = service.check_duplicate(video_path_diff_audio)
    print_result(is_dup3 and dup_ad_id3 == "existing_ad" and "Layer 3" in dup_msg3, f"check_duplicate correctly detected duplicate via Layer 3 (dHash). ID: {dup_ad_id3}, Msg: {dup_msg3}")

    # 9. Test check_duplicate (Integer-like duration correction)
    # Set duration of 'existing_ad' to '2.0' in the database (which is wrong since actual duration is 3.0)
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE download_history SET duration = '2.0' WHERE ad_id = 'existing_ad'")
    conn.commit()
    conn.close()
    
    # Run duplicate check with the same video (actual duration 3.0).
    # Since stored duration is '2.0' (integer-like) and difference is 1.0 (<= 1.5),
    # it should call get_video_duration, correct the stored duration to 3.0, and detect the duplicate!
    is_dup4, dup_ad_id4, dup_msg4 = service.check_duplicate(dest_video_path)
    print_result(is_dup4 and dup_ad_id4 == "existing_ad", f"check_duplicate corrected integer duration from 2.0 to 3.0 and matched. ID: {dup_ad_id4}, Msg: {dup_msg4}")

    # Clean up test environment
    try:
        shutil.rmtree(test_dir)
        print("[*] Cleaned up test_env directory.")
    except Exception as e:
        print(f"[-] Failed to delete test_env directory: {e}")

if __name__ == '__main__':
    run_tests()
