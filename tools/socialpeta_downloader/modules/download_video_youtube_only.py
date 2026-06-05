import os
import sys
import csv
import re
import traceback

# Add project root to sys.path to resolve socialpeta_downloader
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

try:
    from socialpeta_downloader.config import settings
    ffmpeg_path = settings.FFMPEG_PATH
except Exception:
    ffmpeg_path = "ffmpeg"

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

def is_untruncated_youtube_url(url: str) -> bool:
    """
    Check if a YouTube URL is not truncated (contains a full 11-character video ID).
    """
    if not url:
        return False
    # 1. watch?v=ID or &v=ID
    match_v = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
    if match_v:
        vid = match_v.group(1)
        return len(vid) == 11
        
    # 2. youtu.be/ID
    match_short = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if match_short:
        vid = match_short.group(1)
        return len(vid) == 11

    # 3. embed/ID or shorts/ID or v/ID
    match_path = re.search(r'/(?:embed|shorts|v)/([a-zA-Z0-9_-]+)', url)
    if match_path:
        vid = match_path.group(1)
        return len(vid) == 11
        
    return False

def download_direct_mp4(url, output_path):
    """
    Download a video MP4 file directly from CDN using requests.
    """
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    temp_path = output_path + ".cdn.tmp"
    try:
        print(f"    [CDN Fallback] Downloading from CDN: {url}")
        # Use stream=True and a 20-second timeout
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
        print(f"    [SUCCESS] CDN Fallback download complete.")
        return True
    except Exception as e:
        print(f"    [CDN Error] Error downloading CDN URL: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_creatives_1_to_10.csv")
    output_dir = os.path.join(script_dir, "download_video_youtube_only")
    
    print("=" * 80)
    print("YOUTUBE ONLY VIDEO DOWNLOADER")
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
    
    # Filter for unique YouTube URLs
    to_download = []
    seen_urls = set()
    
    for row in rows:
        yt_url = row.get("youtube_url", "").strip()
        # Fallback to video_url if youtube_url is empty but video_url has youtube link
        if not yt_url:
            video_url = row.get("video_url", "").strip()
            if is_youtube_url(video_url):
                yt_url = video_url
                
        if yt_url and is_youtube_url(yt_url):
            if yt_url not in seen_urls:
                seen_urls.add(yt_url)
                # Keep the resolved yt_url in the row dict
                row["youtube_url_resolved"] = yt_url
                to_download.append(row)
                
    total_videos = len(to_download)
    print(f"[+] Found {total_videos} unique YouTube video URLs to download.")
    
    if total_videos == 0:
        print("[*] No YouTube videos to download. Exiting.")
        return
        
    import yt_dlp
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for index, item in enumerate(to_download, 1):
        ad_id = item.get("ad_id", "unknown").strip()
        app_name = item.get("app_name", "UnknownApp").strip()
        youtube_url = item["youtube_url_resolved"]
        video_url = item.get("video_url", "").strip()
        
        cleaned_app_name = sanitize_app_name(app_name)
        # Final filename format: {cleaned_app_name}_{ad_id}.mp4
        final_filename = f"{cleaned_app_name}_{ad_id}.mp4"
        final_path = os.path.join(output_dir, final_filename)
        
        print(f"\n[{index}/{total_videos}] Processing: {app_name} (ID: {ad_id})")
        print(f"    URL: {youtube_url}")
        
        # Check if file already exists
        if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            print(f"    [SKIP] Already downloaded as {final_filename}")
            skip_count += 1
            continue
            
        print(f"    Downloading to: {final_filename}...")
        
        # Check if the youtube URL is truncated or not a valid format
        is_truncated = not is_untruncated_youtube_url(youtube_url)
        has_cdn_fallback = video_url and not is_youtube_url(video_url)
        
        downloaded = False
        
        if not is_truncated:
            temp_output = os.path.join(output_dir, f"{ad_id}_yt.tmp")
            
            # Setup yt-dlp options
            ydl_opts = {
                'outtmpl': temp_output,
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                'merge_output_format': 'mp4',
                'quiet': False,
                'no_warnings': False,
            }
            
            # Configure ffmpeg path if it exists
            if ffmpeg_path and ffmpeg_path != "ffmpeg":
                ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_path)
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                    
                # Locate the output file. yt-dlp might append .mp4 or save as the outtmpl itself
                temp_mp4 = temp_output + ".mp4"
                actual_temp_file = None
                
                if os.path.exists(temp_mp4):
                    actual_temp_file = temp_mp4
                elif os.path.exists(temp_output):
                    actual_temp_file = temp_output
                    
                if actual_temp_file and os.path.exists(actual_temp_file):
                    # Move to final location
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(actual_temp_file, final_path)
                    print(f"    [SUCCESS] Saved via yt-dlp to {final_filename}")
                    success_count += 1
                    downloaded = True
                else:
                    print(f"    [ERROR] yt-dlp download completed but temp output file not found.")
            except Exception as e:
                print(f"    [ERROR] yt-dlp download failed: {e}")
                # Clean up temp files if any
                for suffix in ["", ".mp4", ".f137.mp4", ".f251.webm", ".temp", ".part"]:
                    p = temp_output + suffix
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
        else:
            print(f"    [INFO] YouTube URL is truncated/corrupted: {youtube_url}")
            
        # Fallback to direct MP4 download if yt-dlp failed or was skipped
        if not downloaded:
            if has_cdn_fallback:
                print(f"    [FALLBACK] Attempting CDN fallback download from {video_url}...")
                if download_direct_mp4(video_url, final_path):
                    success_count += 1
                    downloaded = True
                else:
                    fail_count += 1
            else:
                print(f"    [ERROR] No valid CDN fallback video URL available.")
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
