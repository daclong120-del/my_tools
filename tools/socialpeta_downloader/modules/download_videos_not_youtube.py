import os
import sys
import csv
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def sanitize_app_name(app_name):
    """
    Sanitize the app name to be safe for filenames.
    """
    if not app_name:
        return "UnknownApp"
    # Keep alphanumeric characters, spaces, dashes, and underscores
    cleaned = re.sub(r'[^\w\s-]', '', app_name)
    # Replace spaces with underscores
    cleaned = re.sub(r'\s+', '_', cleaned).strip()
    return cleaned if cleaned else "UnknownApp"

def is_youtube_url(url):
    """
    Check if a URL is a YouTube link.
    """
    if not url:
        return False
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u

def download_video(url, output_path):
    """
    Download a video directly from the URL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    temp_path = output_path + ".tmp"
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=20)
        response.raise_for_status()
        
        # Set raw socket read timeout to prevent indefinite hangs
        if response.raw and hasattr(response.raw, "connection") and response.raw.connection:
            try:
                response.raw.connection.sock.settimeout(20.0)
            except Exception:
                pass
                
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        # Replace the final file
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(temp_path, output_path)
        return True
    except Exception as e:
        print(f"    [ERROR] Download failed for {url}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False

def process_row(index, item, output_dir, total_videos):
    """
    Worker function to process and download a single non-YouTube video creative.
    """
    ad_id = item.get("ad_id", "unknown").strip()
    app_name = item.get("app_name", "UnknownApp").strip()
    video_url = item["video_url"].strip()
    
    # Determine the file extension
    ext = ".mp4"
    url_path = video_url.split("?")[0]
    match_ext = re.search(r'\.(\w{3,4})$', url_path)
    if match_ext:
        ext = f".{match_ext.group(1)}"
        
    cleaned_app_name = sanitize_app_name(app_name)
    final_filename = f"{cleaned_app_name}_{ad_id}{ext}"
    final_path = os.path.join(output_dir, final_filename)
    
    # Check if already downloaded and not empty
    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
        return "skip", final_filename, video_url
        
    print(f"[{index}/{total_videos}] Downloading: {final_filename}...")
    success = download_video(video_url, final_path)
    if success:
        return "success", final_filename, video_url
    else:
        return "fail", final_filename, video_url

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_creatives_1_to_10.csv")
    output_dir = os.path.join(script_dir, "download_videos_not_youtube")
    
    print("=" * 80)
    print("PARALLEL NON-YOUTUBE VIDEO DOWNLOADER")
    print(f"Source CSV : {csv_path}")
    print(f"Output Dir : {output_dir}")
    print("=" * 80)
    
    if not os.path.exists(csv_path):
        print(f"[-] Error: CSV file does not exist at {csv_path}")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    
    # Read and parse CSV
    rows = []
    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"[-] Error reading CSV: {e}")
        return
        
    print(f"[+] Total rows found in CSV: {len(rows)}")
    
    # Filter for unique non-YouTube video URLs
    to_download = []
    seen_urls = set()
    
    for row in rows:
        video_url = row.get("video_url", "").strip()
        youtube_url = row.get("youtube_url", "").strip()
        
        # Exclude YouTube videos
        if is_youtube_url(video_url) or is_youtube_url(youtube_url):
            continue
            
        if video_url and video_url.startswith("http"):
            if video_url not in seen_urls:
                seen_urls.add(video_url)
                to_download.append(row)
                
    total_videos = len(to_download)
    print(f"[+] Found {total_videos} unique non-YouTube video URLs to download.")
    
    if total_videos == 0:
        print("[*] No non-YouTube videos to download. Exiting.")
        return
        
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    max_workers = 10
    print(f"[+] Starting download with {max_workers} parallel workers...")
    print("-" * 80)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_row, index, item, output_dir, total_videos): item 
            for index, item in enumerate(to_download, 1)
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                status, filename, url = future.result()
                if status == "success":
                    success_count += 1
                elif status == "skip":
                    skip_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"[-] Thread execution error: {e}")
                fail_count += 1
                
    print("\n" + "=" * 80)
    print("DOWNLOAD COMPLETED SUMMARY")
    print(f"Total Videos processed : {total_videos}")
    print(f"Successfully downloaded: {success_count}")
    print(f"Skipped (already exist): {skip_count}")
    print(f"Failed downloads       : {fail_count}")
    print("=" * 80)

if __name__ == "__main__":
    main()
