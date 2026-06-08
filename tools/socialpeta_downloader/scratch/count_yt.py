import csv

def is_youtube_url(url):
    if not url:
        return False
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u

csv_path = r"c:\Users\daclo\Downloads\New folder (6)\download_info.csv"

try:
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit(1)

to_download = []
seen_urls = set()

for row in rows:
    yt_url = row.get("youtube_url", "").strip()
    video_url = row.get("video_url", "").strip()
    
    if not yt_url:
        if is_youtube_url(video_url):
            yt_url = video_url
        else:
            if video_url:
                continue
                
    if yt_url and is_youtube_url(yt_url):
        if yt_url not in seen_urls:
            seen_urls.add(yt_url)
            to_download.append(yt_url)

print(f"TOTAL_UNIQUE_YOUTUBE_URLS: {len(to_download)}")
for idx, url in enumerate(to_download, 1):
    print(f"{idx}. {url}")
