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
from typing import Optional
from socialpeta_downloader.core.protocols import IEngineContext

class YoutubeService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def _youtube_extract_worker(self):
        """
        Runs on Stream 1 Playwright thread to execute UC-03 click flow safely
        """
        if not self.context:
            return
            
        if self.context.youtube_extract_queue.empty() or not self.context.active_page:
            return
            
        page = self.context.active_page
        item = self.context.youtube_extract_queue.get()
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
                        
                    clicked = page.evaluate(r"""({adId, imageUrl, videoUrl, appName, title, body}) => {
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
                        
                        const cards = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light, [class*="creative-card"]'));
                        let bestCard = null;
                        let maxScore = 0;
                        
                        for (const c of cards) {
                            let score = 0;
                            const cardText = (c.innerText || c.textContent || "").toLowerCase();
                            
                            // 1. So khop bang anh/video hash (20 diem)
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let hashMatched = false;
                            for (const img of imgs) {
                                if (img && img.src) {
                                    if (imgHash && img.src.includes(imgHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                    if (vidHash && img.src.includes(vidHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                }
                            }
                            
                            const videos = Array.from(c.querySelectorAll('video'));
                            for (const video of videos) {
                                if (video && video.src) {
                                    if (vidHash && video.src.includes(vidHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                    if (imgHash && video.src.includes(imgHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                }
                            }
                            
                            if (hashMatched) {
                                score += 20;
                            }
                            
                            // 2. So khop bang App Name (5 diem)
                            if (appName) {
                                const cleanAppName = appName.toLowerCase().trim();
                                if (cleanAppName && cleanAppName !== 'unknownapp') {
                                    if (cardText.includes(cleanAppName)) {
                                        score += 5;
                                    } else {
                                        const words = cleanAppName.split(/\s+/).filter(w => w.length > 2);
                                        let wordMatchCount = 0;
                                        for (const w of words) {
                                            if (cardText.includes(w)) {
                                                wordMatchCount++;
                                            }
                                        }
                                        if (words.length > 0 && wordMatchCount === words.length) {
                                            score += 4;
                                        } else if (wordMatchCount > 0) {
                                            score += 1.5 * wordMatchCount;
                                        }
                                    }
                                }
                            }
                            
                            // 3. So khop bang Title hoac Body (10 diem)
                            if (title) {
                                const cleanTitle = title.toLowerCase().trim();
                                if (cleanTitle) {
                                    if (cardText.includes(cleanTitle)) {
                                        score += 10;
                                    } else if (cleanTitle.length > 15) {
                                        const sub = cleanTitle.substring(0, 15);
                                        if (cardText.includes(sub)) {
                                            score += 5;
                                        }
                                    }
                                }
                            }
                            
                            if (body) {
                                const cleanBody = body.toLowerCase().trim();
                                if (cleanBody) {
                                    if (cardText.includes(cleanBody)) {
                                        score += 10;
                                    } else if (cleanBody.length > 15) {
                                        const sub = cleanBody.substring(0, 15);
                                        if (cardText.includes(sub)) {
                                            score += 5;
                                        }
                                    }
                                }
                            }
                            
                            // 4. Kiem tra icon YouTube tren card (3 diem)
                            const hasYoutubeIcon = !!c.querySelector('.net-icon-youtube') || 
                                                   !!c.querySelector('[class*="net-icon-youtube"]') ||
                                                   !!c.querySelector('[class*="-youtube"]');
                            if (hasYoutubeIcon) {
                                score += 3;
                            }
                            
                            if (score > maxScore) {
                                maxScore = score;
                                bestCard = c;
                            }
                        }
                        
                        if (bestCard && maxScore >= 5) {
                            bestCard.scrollIntoView({behavior: 'instant', block: 'center'});
                            const btn = Array.from(bestCard.querySelectorAll('button, a, [class*="btn"], [class*="detail"]'))
                                .find(el => {
                                    const text = el.textContent || el.innerText || "";
                                    return text.includes("详情") || text.toLowerCase().includes("detail") || text.includes("Chi tiết");
                                }) || bestCard.querySelector('button, [class*="btn"], [class*="detail"], a') || bestCard;
                            btn.click();
                            return true;
                        }
                        return false;
                    }""", {
                        "adId": ad_id,
                        "imageUrl": item.get("image_url", ""),
                        "videoUrl": item.get("video_url", ""),
                        "appName": item.get("app_name", ""),
                        "title": item.get("title", ""),
                        "body": item.get("body", "")
                    })
                    
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
                import traceback
                if self.context:
                    self.context.log("error", f"[YouTube Debug Error] Loi o attempt {attempt}: {e}\n{traceback.format_exc()}")
                else:
                    print(f"[YouTube Debug Error] Loi o attempt {attempt}: {e}\n{traceback.format_exc()}")
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
            
        self.context.utils_service._save_item_state(item)
        
        if success:
            self.context.pending_downloads.put((time.time(), item["fpath"]))

    def _youtube_extract_worker_for_tab(self, tab_index: int, page):
        """
        Processes YouTube iframe extraction for this specific tab page.
        """
        if not self.context:
            return
            
        q = self.context.tab_youtube_queues.get(tab_index)
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
                        
                    clicked = page.evaluate(r"""({adId, imageUrl, videoUrl, appName, title, body}) => {
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
                        
                        const cards = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light, [class*="creative-card"]'));
                        let bestCard = null;
                        let maxScore = 0;
                        
                        for (const c of cards) {
                            let score = 0;
                            const cardText = (c.innerText || c.textContent || "").toLowerCase();
                            
                            // 1. So khop bang anh/video hash (20 diem)
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let hashMatched = false;
                            for (const img of imgs) {
                                if (img && img.src) {
                                    if (imgHash && img.src.includes(imgHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                    if (vidHash && img.src.includes(vidHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                }
                            }
                            
                            const videos = Array.from(c.querySelectorAll('video'));
                            for (const video of videos) {
                                if (video && video.src) {
                                    if (vidHash && video.src.includes(vidHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                    if (imgHash && video.src.includes(imgHash)) {
                                        hashMatched = true;
                                        break;
                                    }
                                }
                            }
                            
                            if (hashMatched) {
                                score += 20;
                            }
                            
                            // 2. So khop bang App Name (5 diem)
                            if (appName) {
                                const cleanAppName = appName.toLowerCase().trim();
                                if (cleanAppName && cleanAppName !== 'unknownapp') {
                                    if (cardText.includes(cleanAppName)) {
                                        score += 5;
                                    } else {
                                        const words = cleanAppName.split(/\s+/).filter(w => w.length > 2);
                                        let wordMatchCount = 0;
                                        for (const w of words) {
                                            if (cardText.includes(w)) {
                                                wordMatchCount++;
                                            }
                                        }
                                        if (words.length > 0 && wordMatchCount === words.length) {
                                            score += 4;
                                        } else if (wordMatchCount > 0) {
                                            score += 1.5 * wordMatchCount;
                                        }
                                    }
                                }
                            }
                            
                            // 3. So khop bang Title hoac Body (10 diem)
                            if (title) {
                                const cleanTitle = title.toLowerCase().trim();
                                if (cleanTitle) {
                                    if (cardText.includes(cleanTitle)) {
                                        score += 10;
                                    } else if (cleanTitle.length > 15) {
                                        const sub = cleanTitle.substring(0, 15);
                                        if (cardText.includes(sub)) {
                                            score += 5;
                                        }
                                    }
                                }
                            }
                            
                            if (body) {
                                const cleanBody = body.toLowerCase().trim();
                                if (cleanBody) {
                                    if (cardText.includes(cleanBody)) {
                                        score += 10;
                                    } else if (cleanBody.length > 15) {
                                        const sub = cleanBody.substring(0, 15);
                                        if (cardText.includes(sub)) {
                                            score += 5;
                                        }
                                    }
                                }
                            }
                            
                            // 4. Kiem tra icon YouTube tren card (3 diem)
                            const hasYoutubeIcon = !!c.querySelector('.net-icon-youtube') || 
                                                   !!c.querySelector('[class*="net-icon-youtube"]') ||
                                                   !!c.querySelector('[class*="-youtube"]');
                            if (hasYoutubeIcon) {
                                score += 3;
                            }
                            
                            if (score > maxScore) {
                                maxScore = score;
                                bestCard = c;
                            }
                        }
                        
                        if (bestCard && maxScore >= 5) {
                            bestCard.scrollIntoView({behavior: 'instant', block: 'center'});
                            const btn = Array.from(bestCard.querySelectorAll('button, a, [class*="btn"], [class*="detail"]'))
                                .find(el => {
                                    const text = el.textContent || el.innerText || "";
                                    return text.includes("详情") || text.toLowerCase().includes("detail") || text.includes("Chi tiết");
                                }) || bestCard.querySelector('button, [class*="btn"], [class*="detail"], a') || bestCard;
                            btn.click();
                            return true;
                        }
                        return false;
                    }""", {
                        "adId": ad_id,
                        "imageUrl": item.get("image_url", ""),
                        "videoUrl": item.get("video_url", ""),
                        "appName": item.get("app_name", ""),
                        "title": item.get("title", ""),
                        "body": item.get("body", "")
                    })
                    
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
                import traceback
                if self.context:
                    self.context.log("error", f"[YouTube Debug Error] Loi o attempt {attempt} (tab {tab_index}): {e}\n{traceback.format_exc()}")
                else:
                    print(f"[YouTube Debug Error] Loi o attempt {attempt} (tab {tab_index}): {e}\n{traceback.format_exc()}")
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
            
            self.context.tab_states[tab_index]["scraped_count"] += 1
        else:
            item["status"] = "failed"
            
        self.context.utils_service._save_item_state(item)
        if success and youtube_url:
            self.context.pending_downloads.put((time.time(), item["fpath"]))
