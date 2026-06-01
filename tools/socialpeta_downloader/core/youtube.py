# tools/socialpeta_downloader/core/youtube.py
"""
Responsibility: Handle YouTube URL extraction by finding iframe or clicking details modal.
"""

import os
import re
import time
import traceback
import queue
import threading
from typing import TYPE_CHECKING, Any, Dict

class YoutubeMixin:
    youtube_extract_queue: queue.Queue
    active_page: Any
    pending_downloads: queue.PriorityQueue
    tab_youtube_queues: Dict[int, queue.Queue]
    tab_states: Dict[int, Dict[str, Any]]
    stats_lock: threading.Lock
    stats: Dict[str, int]

    if TYPE_CHECKING:
        def _save_item_state(self, item: dict) -> None:
            ...


    def _youtube_extract_worker(self):
        """
        Runs on Stream 1 Playwright thread to execute UC-03 click flow safely
        """
        if self.youtube_extract_queue.empty() or not self.active_page:
            return
            
        page = self.active_page
        item = self.youtube_extract_queue.get()
        ad_id = item["ad_id"]
        
        print(f"[YouTube] Dang lay URL cho card {ad_id}")
        
        success = False
        youtube_url = ""
        
        # UC-03a: Modal retry loop
        for attempt in range(3):
            if page.is_closed():
                break
            try:
                # Scroll to top first
                try:
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(0.5)
                except Exception:
                    pass

                clicked = False
                max_scroll = 12000
                scroll_step = 600
                current_scroll = 0
                
                while current_scroll < max_scroll:
                    if page.is_closed():
                        break
                        
                    clicked = page.evaluate("""({adId, imageUrl, videoUrl}) => {
                        const getHash = (url) => {
                            if (!url) return null;
                            const m = url.match(/([a-fA-F0-9]{32})/);
                            if (m) return m[1];
                            const parts = url.split('?')[0].split('/');
                            const file = parts[parts.length - 1];
                            const dotIdx = file.lastIndexOf('.');
                            return dotIdx !== -1 ? file.substring(0, dotIdx) : file;
                        };
                        
                        const imgHash = getHash(imageUrl);
                        const vidHash = getHash(videoUrl);
                        
                        const cards = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light'));
                        let card = null;
                        
                        for (const c of cards) {
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let matched = false;
                            for (const img of imgs) {
                                if (img && img.src) {
                                    if (imgHash && img.src.includes(imgHash)) {
                                        matched = true;
                                        break;
                                    }
                                    if (vidHash && img.src.includes(vidHash)) {
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                            if (matched) {
                                card = c;
                                break;
                            }
                            
                            const videos = Array.from(c.querySelectorAll('video'));
                            for (const video of videos) {
                                if (video && video.src) {
                                    if (vidHash && video.src.includes(vidHash)) {
                                        matched = true;
                                        break;
                                    }
                                    if (imgHash && video.src.includes(imgHash)) {
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                            if (matched) {
                                card = c;
                                break;
                            }
                        }
                        
                        if (card) {
                            card.scrollIntoView({behavior: 'instant', block: 'center'});
                            const btn = Array.from(card.querySelectorAll('button, a, [class*="btn"], [class*="detail"]'))
                                .find(el => {
                                    const text = el.textContent || el.innerText || "";
                                    return text.includes("详情") || text.toLowerCase().includes("detail");
                                }) || card.querySelector('button, [class*="btn"], [class*="detail"], a') || card;
                            btn.click();
                            return true;
                        }
                        return false;
                    }""", {"adId": ad_id, "imageUrl": item.get("image_url", ""), "videoUrl": item.get("video_url", "")})
                    
                    if clicked:
                        break
                        
                    current_scroll += scroll_step
                    try:
                        page.evaluate(f"window.scrollTo(0, {current_scroll})")
                        time.sleep(0.5)
                    except Exception:
                        break
                
                if clicked:
                    # Wait for modal & youtube link to load
                    found_url = ""
                    for poll in range(12):  # 12 * 500ms = 6000ms
                        # 1. Check anchor link
                        a_loc = page.locator("a[href*='youtube.com'], a[href*='youtu.be']").first
                        if a_loc.is_visible():
                            href = a_loc.get_attribute("href")
                            if href:
                                found_url = href.strip()
                                break
                        # 2. Check iframe
                        iframe_loc = page.locator("iframe[src*='youtube.com'], iframe[src*='youtu.be']").first
                        if iframe_loc.is_visible():
                            src = iframe_loc.get_attribute("src")
                            if src:
                                found_url = src.strip()
                                break
                        time.sleep(0.5)
                        
                    if not found_url:
                        # Fallback: check body text
                        try:
                            body_text = page.locator("body").inner_text()
                            urls = re.findall(r'https?://[^\s<>"]*?youtu[^\s<>"]*', body_text)
                            if urls:
                                found_url = urls[0].strip()
                        except Exception:
                            pass
                            
                    if found_url:
                        vid_match = re.search(r'v=([^&#]+)', found_url) or \
                                    re.search(r'embed/([^/?#]+)', found_url) or \
                                    re.search(r'youtu\.be/([^/?#]+)', found_url)
                        if vid_match:
                            vid = vid_match.group(1)
                            youtube_url = f"https://www.youtube.com/watch?v={vid}"
                        else:
                            youtube_url = found_url
                        success = True
                        print(f"[YouTube] Tim thay va chuan hoa URL: {youtube_url}")
                        break
                
                time.sleep(2)
            except Exception as e:
                print(f"[YouTube Debug Error] Loi o attempt {attempt}: {e}")
                traceback.print_exc()
                time.sleep(1)
                
            # Close modal if open before next retry (ESC key)
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

        # Cleanup and close modal
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        if not success:
            print("[YouTube] Khong tim thay URL")
            
        item["youtube_url"] = youtube_url
        item["video_url"] = youtube_url
        
        if youtube_url:
            item["media_type"] = "youtube_video"
            try:
                raw_dur = item.get("duration")
                dur = int(float(raw_dur)) if raw_dur not in (None, "") else 0
            except ValueError:
                dur = 0
            print(f"[YouTube] Dat media_type = youtube_video cho URL: {youtube_url}, duration: {dur}s")
        else:
            item["status"] = "failed"
            
        self._save_item_state(item)
        
        if success:
            self.pending_downloads.put((time.time(), item["fpath"]))

    def _youtube_extract_worker_for_tab(self, tab_index: int, page):
        """
        Processes YouTube iframe extraction for this specific tab page.
        """
        q = self.tab_youtube_queues.get(tab_index)
        if not q or q.empty():
            return
            
        item = q.get()
        ad_id = item["ad_id"]
        
        print(f"[YouTube] Dang lay URL cho card {ad_id}")
        
        success = False
        youtube_url = ""
        for attempt in range(2):
            if page.is_closed():
                break
            try:
                # Scroll to top first
                try:
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(0.5)
                except Exception:
                    pass

                clicked = False
                max_scroll = 5400
                scroll_step = 400
                current_scroll = 0
                
                while current_scroll < max_scroll:
                    if page.is_closed():
                        break
                        
                    clicked = page.evaluate("""({adId, imageUrl, videoUrl}) => {
                        const getHash = (url) => {
                            if (!url) return null;
                            const m = url.match(/([a-fA-F0-9]{32})/);
                            if (m) return m[1];
                            const parts = url.split('?')[0].split('/');
                            const file = parts[parts.length - 1];
                            const dotIdx = file.lastIndexOf('.');
                            return dotIdx !== -1 ? file.substring(0, dotIdx) : file;
                        };
                        
                        const imgHash = getHash(imageUrl);
                        const vidHash = getHash(videoUrl);
                        
                        const cards = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light'));
                        let card = null;
                        
                        for (const c of cards) {
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let matched = false;
                            for (const img of imgs) {
                                if (img && img.src) {
                                    if (imgHash && img.src.includes(imgHash)) {
                                        matched = true;
                                        break;
                                    }
                                    if (vidHash && img.src.includes(vidHash)) {
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                            if (matched) {
                                card = c;
                                break;
                            }
                            
                            const videos = Array.from(c.querySelectorAll('video'));
                            for (const video of videos) {
                                if (video && video.src) {
                                    if (vidHash && video.src.includes(vidHash)) {
                                        matched = true;
                                        break;
                                    }
                                    if (imgHash && video.src.includes(imgHash)) {
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                            if (matched) {
                                card = c;
                                break;
                            }
                        }
                        
                        if (card) {
                            card.scrollIntoView({behavior: 'instant', block: 'center'});
                            card.click();
                            return true;
                        }
                        return false;
                    }""", {"adId": ad_id, "imageUrl": item.get("image_url", ""), "videoUrl": item.get("video_url", "")})
                    
                    if clicked:
                        break
                        
                    current_scroll += scroll_step
                    try:
                        page.evaluate(f"window.scrollTo(0, {current_scroll})")
                        time.sleep(0.2)
                    except Exception:
                        break
                
                if clicked:
                    found_url = ""
                    for poll in range(6):  # 6 * 500ms = 3000ms
                        a_loc = page.locator("a[href*='youtube.com'], a[href*='youtu.be']").first
                        if a_loc.is_visible():
                            href = a_loc.get_attribute("href")
                            if href:
                                found_url = href.strip()
                                break
                        iframe_loc = page.locator("iframe[src*='youtube.com'], iframe[src*='youtu.be']").first
                        if iframe_loc.is_visible():
                            src = iframe_loc.get_attribute("src")
                            if src:
                                found_url = src.strip()
                                break
                        time.sleep(0.5)
                        
                    if not found_url:
                        try:
                            body_text = page.locator("body").inner_text()
                            urls = re.findall(r'https?://[^\s<>"]*?youtu[^\s<>"]*', body_text)
                            if urls:
                                found_url = urls[0].strip()
                        except Exception:
                            pass
                            
                    if found_url:
                        vid_match = re.search(r'v=([^&#]+)', found_url) or \
                                    re.search(r'embed/([^/?#]+)', found_url) or \
                                    re.search(r'youtu\.be/([^/?#]+)', found_url)
                        if vid_match:
                            vid = vid_match.group(1)
                            youtube_url = f"https://www.youtube.com/watch?v={vid}"
                        else:
                            youtube_url = found_url
                        success = True
                        print(f"[YouTube] Tim thay va chuan hoa URL (tab {tab_index}): {youtube_url}")
                        break
                time.sleep(0.5)
            except Exception as e:
                print(f"[YouTube Debug Error] Loi o attempt {attempt} (tab {tab_index}): {e}")
                traceback.print_exc()
                time.sleep(1)
                
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        if not success:
            print("[YouTube] Khong tim thay URL")
            
        item["youtube_url"] = youtube_url
        item["video_url"] = youtube_url
        
        if youtube_url:
            item["media_type"] = "youtube_video"
            try:
                raw_dur = item.get("duration")
                dur = int(float(raw_dur)) if raw_dur not in (None, "") else 0
            except ValueError:
                dur = 0
            print(f"[YouTube] Dat media_type = youtube_video cho URL: {youtube_url}, duration: {dur}s (tab {tab_index})")
            
            self.tab_states[tab_index]["scraped_count"] += 1
            with self.stats_lock:
                self.stats["total_sniffed"] += 1
        else:
            item["status"] = "failed"
            
        self._save_item_state(item)
        if success and youtube_url:
            self.pending_downloads.put((time.time(), item["fpath"]))
