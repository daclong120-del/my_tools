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
from typing import Optional, Union
from socialpeta_downloader.core.protocols import IEngineContext

class YoutubeService:
    # hàm đã hoạt động rồi đừng động vào
    def __init__(self, context: Optional[IEngineContext] = None):
        """
        Khởi tạo dịch vụ trích xuất YouTube URL từ chi tiết quảng cáo.
        """
        self.context = context

    # hàm đã hoạt động rồi đừng động vào
    def _youtube_extract_worker(self):
        """
        Tiến trình chạy trên luồng Playwright để thực hiện quy trình click tìm URL YouTube từ modal chi tiết.
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
                            const hasYoutubeIcon = !!c.querySelector('.net-icon-youtube') || 
                                                   !!c.querySelector('[class*="net-icon-youtube"]') ||
                                                   !!c.querySelector('[class*="-youtube"]');
                            if (!hasYoutubeIcon) {
                                continue;
                            }
                            let score = 0;
                            const cardText = (c.innerText || c.textContent || "").toLowerCase();
                            
                            // 1. So khop bang anh/video hash (20 diem)
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let hashMatched = false;
                            for (const img of imgs) {
                                const urls = [
                                    img.src,
                                    img.getAttribute('src'),
                                    img.getAttribute('data-src'),
                                    img.getAttribute('data-original'),
                                    img.getAttribute('lazy-src'),
                                    img.getAttribute('data-lazy-src')
                                ];
                                for (const url of urls) {
                                    if (url) {
                                        if (imgHash && url.includes(imgHash)) {
                                            hashMatched = true;
                                            break;
                                        }
                                        if (vidHash && url.includes(vidHash)) {
                                            hashMatched = true;
                                            break;
                                        }
                                    }
                                }
                                if (hashMatched) break;
                            }
                            
                            if (!hashMatched) {
                                const videos = Array.from(c.querySelectorAll('video'));
                                for (const video of videos) {
                                    const urls = [
                                        video.src,
                                        video.getAttribute('src'),
                                        video.getAttribute('data-src'),
                                        video.getAttribute('poster'),
                                        video.getAttribute('data-poster')
                                    ];
                                    video.querySelectorAll('source').forEach(srcEl => {
                                        urls.push(srcEl.src);
                                        urls.push(srcEl.getAttribute('src'));
                                        urls.push(srcEl.getAttribute('data-src'));
                                    });
                                    for (const url of urls) {
                                        if (url) {
                                            if (vidHash && url.includes(vidHash)) {
                                                hashMatched = true;
                                                break;
                                            }
                                            if (imgHash && url.includes(imgHash)) {
                                                hashMatched = true;
                                                break;
                                            }
                                        }
                                    }
                                    if (hashMatched) break;
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
                            if (btn.tagName && btn.tagName.toLowerCase() === 'a' && btn.hasAttribute('href')) {
                                const hrefVal = btn.getAttribute('href');
                                if (hrefVal && !hrefVal.includes('javascript') && !hrefVal.startsWith('#')) {
                                    btn.removeAttribute('href');
                                }
                            }
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
                        a_loc = page.locator("a[href*='youtube.com'], a[href*='youtu.be'], a[href*='youtube-nocookie.com']").first
                        if (a_loc.is_visible()):
                            href = a_loc.get_attribute("href")
                            if href:
                                found_url = href.strip()
                                break
                        # 2. Check iframe
                        iframe_loc = page.locator("iframe[src*='youtube.com'], iframe[src*='youtu.be'], iframe[src*='youtube-nocookie.com']").first
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
                            urls = re.findall(r'https?://[^\s<>"]*?(?:youtu|youtube-nocookie)[^\s<>"]*', body_text)
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

        original_video_url = item.get("video_url")
        
        if youtube_url:
            item["youtube_url"] = youtube_url
            item["video_url"] = youtube_url
            item["media_type"] = "youtube_video"
            try:
                raw_dur = item.get("duration")
                dur = int(float(raw_dur)) if raw_dur not in (None, "") else 0
            except ValueError:
                dur = 0
            print(f"[YouTube] Dat media_type = youtube_video cho URL: {youtube_url}, duration: {dur}s")
            self.context.utils_service._save_item_state(item)
            self.context.pending_downloads.put((time.time(), item["fpath"]))
        else:
            if original_video_url and not any(x in original_video_url.lower() for x in ["youtube.com", "youtu.be", "youtube-nocookie.com"]):
                print(f"[YouTube Fallback] Khong lay duoc link YouTube cho Ad {ad_id}, rollback ve video CDN: {original_video_url}")
                item["media_type"] = "video"
                item["status"] = "pending"
                self.context.utils_service._save_item_state(item)
                self.context.pending_downloads.put((time.time(), item["fpath"]))
            else:
                print(f"[YouTube] Khong tim thay URL, ad {ad_id} danh dau that bai")
                item["youtube_url"] = ""
                item["video_url"] = ""
                item["status"] = "failed"
                self.context.utils_service._save_item_state(item)

    # hàm đã hoạt động rồi đừng động vào
    def _youtube_extract_worker_for_tab(self, tab_index: int, page):
        """
        Thực hiện trích xuất URL iframe YouTube cho một tab cụ thể.
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
                            const hasYoutubeIcon = !!c.querySelector('.net-icon-youtube') || 
                                                   !!c.querySelector('[class*="net-icon-youtube"]') ||
                                                   !!c.querySelector('[class*="-youtube"]');
                            if (!hasYoutubeIcon) {
                                continue;
                            }
                            let score = 0;
                            const cardText = (c.innerText || c.textContent || "").toLowerCase();
                            
                            // 1. So khop bang anh/video hash (20 diem)
                            const imgs = Array.from(c.querySelectorAll('img'));
                            let hashMatched = false;
                            for (const img of imgs) {
                                const urls = [
                                    img.src,
                                    img.getAttribute('src'),
                                    img.getAttribute('data-src'),
                                    img.getAttribute('data-original'),
                                    img.getAttribute('lazy-src'),
                                    img.getAttribute('data-lazy-src')
                                ];
                                for (const url of urls) {
                                    if (url) {
                                        if (imgHash && url.includes(imgHash)) {
                                            hashMatched = true;
                                            break;
                                        }
                                        if (vidHash && url.includes(vidHash)) {
                                            hashMatched = true;
                                            break;
                                        }
                                    }
                                }
                                if (hashMatched) break;
                            }
                            
                            if (!hashMatched) {
                                const videos = Array.from(c.querySelectorAll('video'));
                                for (const video of videos) {
                                    const urls = [
                                        video.src,
                                        video.getAttribute('src'),
                                        video.getAttribute('data-src'),
                                        video.getAttribute('poster'),
                                        video.getAttribute('data-poster')
                                    ];
                                    video.querySelectorAll('source').forEach(srcEl => {
                                        urls.push(srcEl.src);
                                        urls.push(srcEl.getAttribute('src'));
                                        urls.push(srcEl.getAttribute('data-src'));
                                    });
                                    for (const url of urls) {
                                        if (url) {
                                            if (vidHash && url.includes(vidHash)) {
                                                hashMatched = true;
                                                break;
                                            }
                                            if (imgHash && url.includes(imgHash)) {
                                                hashMatched = true;
                                                break;
                                            }
                                        }
                                    }
                                    if (hashMatched) break;
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
                            if (btn.tagName && btn.tagName.toLowerCase() === 'a' && btn.hasAttribute('href')) {
                                const hrefVal = btn.getAttribute('href');
                                if (hrefVal && !hrefVal.includes('javascript') && !hrefVal.startsWith('#')) {
                                    btn.removeAttribute('href');
                                }
                            }
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
                        a_loc = page.locator("a[href*='youtube.com'], a[href*='youtu.be'], a[href*='youtube-nocookie.com']").first
                        if (a_loc.is_visible()):
                            href = a_loc.get_attribute("href")
                            if href:
                                found_url = href.strip()
                                break
                        iframe_loc = page.locator("iframe[src*='youtube.com'], iframe[src*='youtu.be'], iframe[src*='youtube-nocookie.com']").first
                        if iframe_loc.is_visible():
                            src = iframe_loc.get_attribute("src")
                            if src:
                                found_url = src.strip()
                                break
                        time.sleep(0.5)
                        
                    if not found_url:
                        try:
                            body_text = page.locator("body").inner_text()
                            urls = re.findall(r'https?://[^\s<>"]*?(?:youtu|youtube-nocookie)[^\s<>"]*', body_text)
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

        original_video_url = item.get("video_url")
        
        if youtube_url:
            item["youtube_url"] = youtube_url
            item["video_url"] = youtube_url
            item["media_type"] = "youtube_video"
            try:
                raw_dur = item.get("duration")
                dur = int(float(raw_dur)) if raw_dur not in (None, "") else 0
            except ValueError:
                dur = 0
            print(f"[YouTube] Dat media_type = youtube_video cho URL: {youtube_url}, duration: {dur}s (tab {tab_index})")
            
            self.context.tab_states[tab_index]["scraped_count"] += 1
            self.context.utils_service._save_item_state(item)
            self.context.pending_downloads.put((time.time(), item["fpath"]))
        else:
            if original_video_url and not any(x in original_video_url.lower() for x in ["youtube.com", "youtu.be", "youtube-nocookie.com"]):
                print(f"[YouTube Fallback] Khong lay duoc link YouTube cho Ad {ad_id}, rollback ve video CDN: {original_video_url}")
                item["media_type"] = "video"
                item["status"] = "pending"
                self.context.utils_service._save_item_state(item)
                self.context.pending_downloads.put((time.time(), item["fpath"]))
            else:
                print(f"[YouTube] Khong tim thay URL, ad {ad_id} danh dau that bai")
                item["youtube_url"] = ""
                item["video_url"] = ""
                item["status"] = "failed"
                self.context.utils_service._save_item_state(item)

    def clear_youtube_processed_attributes(self, page) -> None:
        """
        Dọn dẹp thuộc tính tạm data-youtube-processed trên giao diện để tránh kẹt trạng thái.
        """
        try:
            page.evaluate("""() => {
                document.querySelectorAll('[data-youtube-processed]').forEach(el => {
                    el.removeAttribute('data-youtube-processed');
                });
            }""")
        except Exception:
            pass

    # hàm đã hoạt động rồi đừng động vào
    def click_and_extract_youtube_from_page(self, page) -> list:
        """
        Quét giao diện, click vào nút Chi tiết (Detail) của từng card có icon YouTube để mở modal, 
        trích xuất đường dẫn YouTube và đóng modal.
        """
        self.clear_youtube_processed_attributes(page)
        results = []
        # 1. Cuộn trang xuống để load hết các card trên giao diện trước
        print("[*] Đang cuộn trang để tải đầy đủ các card quảng cáo...")
        try:
            for i in range(1, 6):
                page.evaluate(f"window.scrollTo(0, {i * 2000})")
                time.sleep(0.08)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.1)
        except Exception:
            pass
            
        print("[*] Bắt đầu quét và click vào từng card có icon YouTube...")
        
        while True:
            # Tìm và click vào card chưa xử lý kế tiếp
            clicked = page.evaluate("""() => {
                const card = Array.from(document.querySelectorAll('.creative-card-item, .shadow-common-light, [class*="creative-card"]'))
                    .find(c => {
                        const hasYoutube = !!c.querySelector('.net-icon-youtube') || 
                                           !!c.querySelector('[class*="net-icon-youtube"]') ||
                                           !!c.querySelector('[class*="-youtube"]');
                        return hasYoutube && !c.hasAttribute('data-youtube-processed');
                    });
                if (card) {
                    card.setAttribute('data-youtube-processed', 'true');
                    card.scrollIntoView({behavior: 'instant', block: 'center'});
                    
                    const cardText = card.innerText || card.textContent || "";
                    const idMatch = cardText.match(/ID:\\s*(\\d+)/) || cardText.match(/(\\d{9,18})/);
                    const adId = idMatch ? idMatch[1] : "";
                    
                    let appName = "";
                    const appEl = card.querySelector('.app-name, [class*="app-name"], .name, [class*="name"]');
                    if (appEl) {
                        appName = appEl.innerText || appEl.textContent || "";
                    } else {
                        const lines = cardText.split('\\n').map(l => l.trim()).filter(Boolean);
                        if (lines.length > 0) appName = lines[0];
                    }
                    
                    const btn = Array.from(card.querySelectorAll('button, a, [class*="btn"], [class*="detail"]'))
                        .find(el => {
                            const text = el.textContent || el.innerText || "";
                            return text.includes("详情") || text.toLowerCase().includes("detail") || text.includes("Chi tiết");
                        }) || card.querySelector('button, [class*="btn"], [class*="detail"], a') || card;
                    
                    if (btn.tagName && btn.tagName.toLowerCase() === 'a' && btn.hasAttribute('href')) {
                        const hrefVal = btn.getAttribute('href');
                        if (hrefVal && !hrefVal.includes('javascript') && !hrefVal.startsWith('#')) {
                            btn.removeAttribute('href');
                        }
                    }
                    btn.click();
                    return { success: true, adId: adId, appName: appName.trim(), cardText: cardText };
                }
                return { success: false };
            }""")
            
            if not clicked.get("success"):
                # Không còn card nào có icon YouTube chưa được xử lý
                break
                
            ad_id = clicked.get("adId", "")
            app_name = clicked.get("appName", "")
            print(f"[*] Đã click mở modal của card YouTube (ID: {ad_id}, App: {app_name}). Đang tìm link YouTube...")
            
            # Đợi modal xuất hiện và load link YouTube
            found_url = ""
            for poll in range(25):  # 25 * 80ms = 2s max wait
                # 1. Tìm thẻ <a> có link youtube
                a_loc = page.locator("a[href*='youtube.com'], a[href*='youtu.be'], a[href*='youtube-nocookie.com']").first
                if a_loc.is_visible():
                    href = a_loc.get_attribute("href")
                    if href:
                        found_url = href.strip()
                        break
                # 2. Tìm thẻ <iframe> có src youtube
                iframe_loc = page.locator("iframe[src*='youtube.com'], iframe[src*='youtu.be'], iframe[src*='youtube-nocookie.com']").first
                if iframe_loc.is_visible():
                    src = iframe_loc.get_attribute("src")
                    if src:
                        found_url = src.strip()
                        break
                time.sleep(0.08)
                
            if not found_url:
                # Tìm trong body text của modal làm phương án dự phòng
                try:
                    body_text = page.locator("body").inner_text()
                    urls = re.findall(r'https?://[^\s<>"]*?(?:youtu|youtube-nocookie)[^\s<>"]*', body_text)
                    if urls:
                        found_url = urls[0].strip()
                        # Loại bỏ các dấu chấm hoặc ký tự ellipsis ở cuối link nếu có
                        found_url = re.sub(r'[\s.…]+$', '', found_url)
                except Exception:
                    pass
            
            # Đọc title/body từ modal
            title = ""
            body = ""
            try:
                modal_el = page.locator(".el-dialog, .modal, [class*='dialog'], [class*='modal']").first
                if modal_el.is_visible():
                    modal_text = modal_el.inner_text()
                    lines = [l.strip() for l in modal_text.split("\n") if l.strip()]
                    if lines:
                        body = "\n".join(lines[:3])
            except Exception:
                pass
 
            youtube_url = ""
            if found_url:
                vid_match = re.search(r'v=([^&#]+)', found_url) or \
                            re.search(r'embed/([^/?#]+)', found_url) or \
                            re.search(r'youtu\.be/([^/?#]+)', found_url)
                if vid_match:
                    vid = vid_match.group(1)
                    youtube_url = f"https://www.youtube.com/watch?v={vid}"
                else:
                    youtube_url = found_url
                print(f"[+] Tìm thấy link YouTube: {youtube_url}")
                results.append({
                    "ad_id": ad_id,
                    "app_name": app_name,
                    "youtube_url": youtube_url,
                    "title": title,
                    "body": body
                })
            else:
                print("[-] Không tìm thấy link YouTube cho card này.")
                
            # Đóng modal (ấn Escape)
            try:
                page.keyboard.press("Escape")
                time.sleep(0.2)
            except Exception:
                pass
                
        # Xóa các attribute tạm để không ảnh hưởng đến các lần quét sau
        self.clear_youtube_processed_attributes(page)
            
        return results

    def run_click_youtube_icons_cli(self, argv: Optional[list] = None) -> None:
        """
        CLI để kết nối Chrome, quét và click icon YouTube trên trang hiện tại để trích xuất link.
        Tương tự logic cũ trong click_youtube_icons.py.
        """
        if not self.context:
            from socialpeta_downloader.core import SocialPetaDownloaderCore
            self.context = SocialPetaDownloaderCore(skip_db_init=True)
            
        from playwright.sync_api import sync_playwright
        port = 9222
        
        print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
        
        with sync_playwright() as p:
            browser, page = self.context.connect_to_active_tab(p, port)
            if not page:
                print("[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
                return
                
            print("[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
            try:
                current_page = self.context.utils_service.get_current_page(page)
                print(f"[+] Bạn đang ở trang: {current_page}")
            except Exception as e:
                print(f"[*] Không đọc được trang hiện tại: {e}")
            
            print("[*] Bắt đầu quét và click từng icon YouTube trên trang hiện tại để trích xuất link...")
            results = self.click_and_extract_youtube_from_page(page)
            
            if not results:
                print("[-] Không tìm thấy hoặc không trích xuất được link YouTube nào trên trang này.")
                browser.close()
                return
                
            print(f"\n[🏁] Hoàn tất! Trích xuất được {len(results)} đường dẫn YouTube:")
            
            for idx, res in enumerate(results, 1):
                youtube_url = res.get("youtube_url")
                ad_id = res.get("ad_id")
                app_name = res.get("app_name")
                print(f"  {idx}. ID: {ad_id} | App: {app_name} | URL: {youtube_url}")
                
            browser.close()
            print(f"\n[🏁] Xử lý xong {len(results)} quảng cáo YouTube trên trang.")

    def run_filter_youtube_creatives_cli(
        self,
        argv: Optional[list] = None,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None
    ) -> None:
        """
        CLI để lọc dữ liệu CSV thô chỉ lấy các dòng chứa link YouTube.
        """
        import csv
        
        core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        modules_dir = os.path.join(core_dir, "modules")
        
        # Mặc định file
        default_input = os.path.join(modules_dir, "scraped_creatives_1_to_10.csv")
        default_output = os.path.join(modules_dir, "scraped_creatives_youtube_only.csv")
        
        argv_args = []
        if argv:
            if len(argv) > 0 and argv[0].endswith(".py"):
                argv_args = argv[1:]
            else:
                argv_args = argv
                
        inp = input_file
        if not inp:
            if len(argv_args) > 0:
                inp = argv_args[0]
            else:
                inp = default_input
                
        out = output_file
        if not out:
            if len(argv_args) > 1:
                out = argv_args[1]
            else:
                out = default_output
            
        if not os.path.exists(inp):
            print(f"[-] Input file not found: {inp}")
            return
            
        print(f"[*] Reading data from: {inp}...")
        
        filtered_rows = []
        total_rows = 0
        
        with open(inp, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            for row in reader:
                total_rows += 1
                if row.get('youtube_url') and row['youtube_url'].strip():
                    filtered_rows.append(row)
                    
        print(f"[*] Total rows scanned: {total_rows}")
        print(f"[*] Found {len(filtered_rows)} rows containing a YouTube link.")
        
        print(f"[*] Writing results to: {out}...")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_rows)
            
        print(f"[+] Done! Created file: {out}")

    def run_download_video_youtube_only_cli(
        self,
        argv: Optional[list] = None,
        csv_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_workers: int = 5
    ) -> None:
        """
        CLI để tải video YouTube từ file CSV chỉ định với cấu hình linh hoạt.
        Tương tự logic cũ trong download_video_youtube_only.py.
        """
        if not self.context:
            from socialpeta_downloader.core import SocialPetaDownloaderCore
            self.context = SocialPetaDownloaderCore(skip_db_init=True)
            
        import csv
        import requests
        import argparse
        
        core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        modules_dir = os.path.join(core_dir, "modules")
        
        default_csv = os.path.join(modules_dir, "scraped_creatives_1_to_10.csv")
        default_out = os.path.join(modules_dir, "download_video_youtube_only")
        
        # Phân tích argv nếu có truyền vào
        if argv is not None:
            # Loại bỏ script name ở đầu nếu argv được truyền trực tiếp từ sys.argv
            parse_args = argv[1:] if len(argv) > 0 and not argv[0].startswith("-") else argv
            parser = argparse.ArgumentParser(description="Parallel YouTube Downloader")
            parser.add_argument("--csv", type=str, default=None, help="Path to source CSV file")
            parser.add_argument("--out", type=str, default=None, help="Path to output directory")
            parser.add_argument("--workers", type=int, default=5, help="Number of parallel worker threads")
            args = parser.parse_args(parse_args)
            csv_path = args.csv or csv_path or default_csv
            output_dir = args.out or output_dir or default_out
            max_workers = args.workers
        else:
            csv_path = csv_path or default_csv
            output_dir = output_dir or default_out
            
        # Hàm helper log tích hợp
        def _log(level: str, msg: str):
            if self.context and hasattr(self.context, "utils_service") and self.context.utils_service:
                self.context.utils_service.log(level, msg)
            else:
                prefix = "[*]" if level == "info" else f"[{level.upper()}]"
                print(f"{prefix} {msg}")

        _log("info", "=" * 80)
        _log("info", "YOUTUBE ONLY VIDEO DOWNLOADER")
        _log("info", f"Source CSV : {csv_path}")
        _log("info", f"Output Dir : {output_dir}")
        _log("info", "=" * 80)
        
        if not os.path.exists(csv_path):
            _log("error", f"CSV file does not exist at {csv_path}")
            return
            
        os.makedirs(output_dir, exist_ok=True)
        
        rows = []
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            _log("error", f"Error reading CSV: {e}")
            return
            
        _log("info", f"Total rows found in CSV: {len(rows)}")
        
        def is_youtube_url(url):
            if not url:
                return False
            u = url.lower()
            return "youtube.com" in u or "youtu.be" in u
            
        def is_untruncated_youtube_url(url: str) -> bool:
            if not url:
                return False
            match_v = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
            if match_v and len(match_v.group(1)) == 11:
                return True
            match_short = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
            if match_short and len(match_short.group(1)) == 11:
                return True
            match_path = re.search(r'/(?:embed|shorts|v)/([a-zA-Z0-9_-]+)', url)
            if match_path and len(match_path.group(1)) == 11:
                return True
            return False
            

        def download_direct_mp4(url, out_path):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            temp_path = out_path + ".cdn.tmp"
            try:
                _log("info", f"Downloading from CDN: {url}")
                response = requests.get(url, headers=headers, stream=True, timeout=20)
                response.raise_for_status()
                if response.raw and hasattr(response.raw, "connection") and response.raw.connection:
                    try:
                        response.raw.connection.sock.settimeout(20.0)
                    except Exception:
                        pass
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(out_path):
                    os.remove(out_path)
                os.rename(temp_path, out_path)
                _log("info", "CDN Fallback download complete.")
                return True
            except Exception as e:
                _log("error", f"Error downloading CDN URL: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                return False
                
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
                    row["youtube_url_resolved"] = yt_url
                    to_download.append(row)
                    
        total_videos = len(to_download)
        _log("info", f"Found {total_videos} unique YouTube video URLs to download.")
        
        if total_videos == 0:
            _log("info", "No YouTube videos to download. Exiting.")
            return
            
        from concurrent.futures import ThreadPoolExecutor
        import yt_dlp
        from socialpeta_downloader.config import settings
        ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        _log("info", f"Starting download with {max_workers} parallel workers...")
        _log("info", "-" * 80)
        
        def _download_yt_task(index, item):
            ad_id = item.get("ad_id", "unknown").strip()
            app_name = item.get("app_name", "UnknownApp").strip()
            youtube_url = item["youtube_url_resolved"]
            video_url = item.get("video_url", "").strip()
            
            video_name = item.get("video_name", "").strip()
            if video_name:
                final_filename = video_name
            else:
                final_filename, _ = self.context.utils_service.get_unique_filename(app_name)
            final_path = os.path.join(output_dir, final_filename)
            
            _log("info", f"[{index}/{total_videos}] Processing: {app_name} (ID: {ad_id}) -> {final_filename}")
            
            # if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            #     _log("info", f"Already downloaded as {final_filename}")
            #     return "skip", final_filename
                
            is_truncated = not is_untruncated_youtube_url(youtube_url)
            has_cdn_fallback = video_url and not is_youtube_url(video_url)
            downloaded = False
            
            if not is_truncated:
                temp_output = os.path.join(output_dir, f"{ad_id}_yt.tmp")
                ydl_opts = {
                    'outtmpl': temp_output,
                    'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                }
                if ffmpeg_path and ffmpeg_path != "ffmpeg":
                    ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_path)
                    
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([youtube_url])
                    temp_mp4 = temp_output + ".mp4"
                    actual_temp_file = None
                    if os.path.exists(temp_mp4):
                        actual_temp_file = temp_mp4
                    elif os.path.exists(temp_output):
                        actual_temp_file = temp_output
                        
                    if actual_temp_file and os.path.exists(actual_temp_file):
                        if os.path.exists(final_path):
                            os.remove(final_path)
                        os.rename(actual_temp_file, final_path)
                        _log("info", f"Saved via yt-dlp to {final_filename}")
                        downloaded = True
                        return "success", final_filename
                    else:
                        _log("error", f"yt-dlp download completed for {final_filename} but temp output file not found.")
                except Exception as e:
                    _log("error", f"yt-dlp download failed for {final_filename}: {e}")
                    for suffix in ["", ".mp4", ".f137.mp4", ".f251.webm", ".temp", ".part"]:
                        p = temp_output + suffix
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
            else:
                _log("info", f"YouTube URL is truncated/corrupted: {youtube_url}")
                
            if not downloaded:
                if has_cdn_fallback:
                    _log("info", f"Attempting CDN fallback download for {final_filename} from {video_url}...")
                    if download_direct_mp4(video_url, final_path):
                        return "success", final_filename
                    else:
                        return "fail", final_filename
                else:
                    _log("error", f"No valid CDN fallback video URL available for {final_filename}.")
                    return "fail", final_filename

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_download_yt_task, index, item): item 
                for index, item in enumerate(to_download, 1)
            }
            
            for future in futures:
                try:
                    result_status, fname = future.result()
                    if result_status == "success":
                        success_count += 1
                    elif result_status == "skip":
                        skip_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    _log("error", f"Future failed: {e}")
                    fail_count += 1
                    
        _log("info", "\n" + "=" * 80)
        _log("info", "DOWNLOAD COMPLETED SUMMARY")
        _log("info", f"Total Videos processed : {total_videos}")
        _log("info", f"Successfully downloaded: {success_count}")
        _log("info", f"Skipped (already exist): {skip_count}")
        _log("info", f"Failed downloads       : {fail_count}")
        _log("info", "=" * 80)

    def run_scrape_current_page_yt_cli(self, argv: Optional[list] = None, csv_path: Optional[str] = None, port: int = 9222) -> None:
        """
        CLI để cào trang hiện tại dùng trang tạm, click và trích xuất link YouTube, lưu kết quả đè scraped_creatives_raw.csv.
        Tương tự logic cũ trong scrape_current_page_yt.py.
        """
        if not self.context:
            from socialpeta_downloader.core import SocialPetaDownloaderCore
            self.context = SocialPetaDownloaderCore(skip_db_init=True)
            
        from playwright.sync_api import sync_playwright
        import csv
        
        if not csv_path:
            core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            modules_dir = os.path.join(core_dir, "modules")
            csv_path = os.path.join(modules_dir, "scraped_creatives_raw.csv")
            
            if argv and len(argv) > 1:
                csv_path = argv[1]
            
        print(f"[*] File CSV đầu ra: {csv_path}")
        print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
        
        def overwrite_raw_csv(filepath, rows):
            fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                          "duration", "impression", "heat", "platform", "download_time",
                          "publisher", "app_name", "area", "copywriting_language", "title",
                          "body", "deployment_time", "saved_path", "file_size"]
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    clean_row = {k: row.get(k, "") for k in fieldnames}
                    writer.writerow(clean_row)
                    
        with sync_playwright() as p:
            browser, page = self.context.connect_to_active_tab(p, port)
            if not page:
                print("[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
                return
                
            print("[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
            current_page = self.context.utils_service.get_current_page(page)
            print(f"[+] Bạn đang ở trang: {current_page}")
            
            temp_page = 2 if current_page == 1 else current_page - 1
            print(f"[*] Trang tạm được chọn để chuyển đổi: Trang {temp_page}")
            
            try:
                # Bước 1: Di chuyển tạm sang trang khác
                print(f"[*] Bước 1: Đang chuyển tạm sang Trang {temp_page}...")
                success_temp = self.context.sniffer_service._navigate_to_page(page, temp_page)
                if not success_temp:
                    print("[-] Thất bại khi di chuyển sang trang tạm.")
                    browser.close()
                    return
                time.sleep(2.0)
                
                # Bước 2: Lắng nghe phản hồi API và quay trở lại trang gốc
                print(f"[*] Bước 2: Quay lại Trang gốc {current_page} và bắt gói tin API...")
                with page.expect_response(lambda r: "/creative/list" in r.url or "/creative-rank/list" in r.url, timeout=20000) as response_info:
                    success_back = self.context.sniffer_service._navigate_to_page(page, current_page)
                    if not success_back:
                        print("[-] Thất bại khi quay lại trang gốc.")
                        browser.close()
                        return
                        
                response = response_info.value
                url = response.url
                print(f"[+] Đã nhận phản hồi từ API URL: {url}")
                time.sleep(1.5)
                
                # Bước 3: Kiểm tra xem đã thực sự quay lại đúng trang gốc chưa
                actual_page = self.context.utils_service.get_current_page(page)
                print(f"[*] Kiểm tra UI: Trang hiện tại hiển thị trên giao diện là {actual_page}")
                if actual_page != current_page:
                    print(f"[-] Lỗi: Giao diện UI chưa quay về trang gốc ({current_page}) mà đang ở {actual_page}. Dừng cào dữ liệu.")
                    browser.close()
                    return
                    
                body = response.json()
                raw_items = self.context.sniffer_service._recursive_find_creatives(body)
                if raw_items:
                    print(f"[📡] Bắt được {len(raw_items)} quảng cáo của Trang gốc {current_page}.")
                    parsed_items = []
                    for raw in raw_items:
                        parsed = self.context.utils_service._parse_creative_item(raw)
                        if parsed.get("ad_id"):
                            parsed_items.append(parsed)
                            
                    has_youtube_to_scrape = False
                    for item in parsed_items:
                        platform = item.get("platform", "").lower()
                        media_type = item.get("media_type", "")
                        yt_url = item.get("youtube_url", "")
                        is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                        has_valid_yt = ("youtube.com" in yt_url.lower() or "youtu.be" in yt_url.lower())
                        if is_yt and not has_valid_yt:
                            has_youtube_to_scrape = True
                            break
                            
                    if has_youtube_to_scrape:
                        print("[*] Phát hiện quảng cáo YouTube cần lấy link. Bắt đầu quét và click từng icon trên trang...")
                        results = self.click_and_extract_youtube_from_page(page)
                        if results:
                            print(f"[*] Đang tiến hành khớp nối link YouTube vừa cào vào danh sách quảng cáo...")
                            for res in results:
                                res_ad_id = str(res.get("ad_id", "")).strip()
                                res_url = str(res.get("youtube_url", "")).strip()
                                if not res_ad_id or not res_url:
                                    continue
                                matched = False
                                for item in parsed_items:
                                    item_ad_id = str(item.get("ad_id", "")).strip()
                                    if item_ad_id == res_ad_id:
                                        item["youtube_url"] = res_url
                                        if item.get("media_type") == "youtube_click_required":
                                            item["media_type"] = "youtube_video"
                                        matched = True
                                        print(f"  [✓] Cập nhật (khớp ID {res_ad_id}): {res_url}")
                                        break
                                if not matched:
                                    res_app_clean = self.context.clean_app_name(res.get("app_name", ""))
                                    if res_app_clean:
                                        for item in parsed_items:
                                            item_app_clean = self.context.clean_app_name(item.get("app_name", ""))
                                            if item_app_clean == res_app_clean:
                                                item_platform = item.get("platform", "").lower()
                                                item_media_type = item.get("media_type", "")
                                                is_item_yt = (item_platform == "youtube" or item_media_type in ["youtube_video", "youtube_click_required"])
                                                old_url = str(item.get("youtube_url", "")).strip()
                                                if is_item_yt and (not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower())):
                                                    item["youtube_url"] = res_url
                                                    if item.get("media_type") == "youtube_click_required":
                                                        item["media_type"] = "youtube_video"
                                                    matched = True
                                                    print(f"  [~] Cập nhật (khớp App '{res_app_clean}', ID {item.get('ad_id')}): {res_url}")
                                                    break
                        else:
                            print("[-] Không cào được link YouTube nào trên trang.")
                    overwrite_raw_csv(csv_path, parsed_items)
                    print(f"[+] Đã ghi đè {len(parsed_items)} quảng cáo của trang hiện tại vào file CSV thô.")
                else:
                    print("[-] Không tìm thấy quảng cáo nào trong phản hồi API.")
            except Exception as e:
                print(f"[-] Lỗi trong quá trình di chuyển trang hoặc xử lý phản hồi API: {e}")
                
            try:
                print("[*] Đang xóa dấu vết (thuộc tính processed) trên trang...")
                self.clear_youtube_processed_attributes(page)
            except Exception as e:
                print(f"[WARN] Lỗi khi xóa dấu vết: {e}")
                
            browser.close()
            print(f"\n[🏁] Hoàn tất cào trang {current_page}.")

    def run_scrape_pages_yt_cli(
        self,
        start_page: Union[int, list, None] = 1,
        end_page: int = 10,
        csv_path: Optional[str] = None,
        argv: Optional[list] = None,
        progress_callback: Optional[callable] = None,
        port: int = 9222
    ) -> dict:
        """
        CLI / API to scrape from start_page to end_page, capture API response and click YouTube to extract URLs,
        saving results into csv_path.
        """
        if not self.context:
            from socialpeta_downloader.core import SocialPetaDownloaderCore
            self.context = SocialPetaDownloaderCore(skip_db_init=True)
            
        from playwright.sync_api import sync_playwright
        import csv
        
        start_page_val = 1
        if isinstance(start_page, list):
            argv = start_page
        elif isinstance(start_page, int):
            start_page_val = start_page
            
        if argv and len(argv) > 1:
            try:
                parts = argv[1].split("-")
                if len(parts) == 2:
                    start_page_val = int(parts[0])
                    end_page = int(parts[1])
                else:
                    end_page = int(argv[1])
            except ValueError:
                csv_path = argv[1]
        if argv and len(argv) > 2:
            csv_path = argv[2]
            
        start_page = start_page_val
            
        if not csv_path:
            core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            modules_dir = os.path.join(core_dir, "modules")
            csv_path = os.path.join(modules_dir, "scraped_creatives_1_to_10.csv")
            
        fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                      "duration", "impression", "heat", "platform", "download_time",
                      "publisher", "app_name", "area", "copywriting_language", "title",
                      "body", "deployment_time", "saved_path", "file_size"]
                      
        # Helper to print, log, and callback
        def report(status_type: str, message: str, extra: Optional[dict] = None):
            if self.context:
                self.context.log("error" if status_type == "error" else "info", message)
            else:
                print(message)
            if progress_callback:
                payload = {"type": status_type, "message": message}
                if extra:
                    payload.update(extra)
                try:
                    progress_callback(payload)
                except Exception as cb_err:
                    print(f"[Callback Error] {cb_err}")

        report("start", f"[*] File CSV đầu ra: {csv_path}", extra={"csv_path": csv_path})
        report("info", f"[*] Cào từ trang {start_page} đến trang {end_page}", extra={"start_page": start_page, "end_page": end_page})
        report("info", f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng 9222...")
        
        total_scraped = 0
        total_youtube_matched = 0
        pages_scraped = []
        
        def is_untruncated_youtube_url(url: str) -> bool:
            if not url:
                return False
            match_v = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
            if match_v and len(match_v.group(1)) == 11:
                return True
            match_short = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
            if match_short and len(match_short.group(1)) == 11:
                return True
            match_path = re.search(r'/(?:embed|shorts|v)/([a-zA-Z0-9_-]+)', url)
            if match_path and len(match_path.group(1)) == 11:
                return True
            return False
            
        def append_to_csv_report(filepath, rows):
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                for row in rows:
                    clean_row = {k: row.get(k, "") for k in fieldnames}
                    writer.writerow(clean_row)
                    
        with sync_playwright() as p:
            browser, page = self.context.connect_to_active_tab(p, port)
            if not page:
                report("error", "[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
                return {
                    "status": "error",
                    "message": "Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được."
                }
                
            report("info", "[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
            try:
                current_page = self.context.utils_service.get_current_page(page)
                report("info", f"[+] Bạn đang ở trang: {current_page}")
            except Exception as e:
                report("warning", f"[WARN] Không đọc được số trang hiện tại từ UI, mặc định coi là 1. Chi tiết: {e}")
                current_page = 1
                
            # Khởi tạo/ghi đè file CSV trống có tiêu đề
            os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
            with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
            if current_page == start_page:
                temp_page = start_page + 1 if start_page == 1 else start_page - 1
                report("info", f"[*] Đang chuyển sang Trang {temp_page} tạm thời để kích hoạt lại API khi quay về Trang {start_page}...")
                success_temp = self.context.sniffer_service._navigate_to_page(page, temp_page)
                if not success_temp:
                    report("warning", f"[-] Thất bại khi di chuyển sang trang tạm {temp_page}.")
                time.sleep(3.0)
                
            for p_num in range(start_page, end_page + 1):
                report("page_start", f"\n[🚀] Bắt đầu cào dữ liệu cho Trang {p_num}/{end_page}...", extra={"page": p_num})
                try:
                    report("info", f"[*] Đang điều hướng đến Trang {p_num} và chờ bắt gói tin API...")
                    with page.expect_response(
                        lambda r: "/creative/list" in r.url or "/creative-rank/list" in r.url,
                        timeout=30000
                    ) as response_info:
                        success_nav = self.context.sniffer_service._navigate_to_page(page, p_num)
                        if not success_nav:
                            report("error", f"[-] Thất bại khi điều hướng đến Trang {p_num}.")
                            continue
                            
                    response = response_info.value
                    url = response.url
                    report("info", f"[+] Đã nhận phản hồi từ API URL: {url}")
                    time.sleep(1.5)
                    
                    actual_page = self.context.utils_service.get_current_page(page)
                    report("info", f"[*] Kiểm tra UI: Trang hiện tại hiển thị trên giao diện là {actual_page}")
                    if actual_page != p_num:
                        report("warning", f"[WARN] Cảnh báo: Giao diện hiển thị trang {actual_page} khác với mục tiêu {p_num}!")
                        
                    body = response.json()
                    raw_items = self.context.sniffer_service._recursive_find_creatives(body)
                    parsed_items = []
                    if raw_items:
                        report("info", f"[📡] Bắt được {len(raw_items)} quảng cáo thô từ API phản hồi của Trang {p_num}.")
                        for raw in raw_items:
                            parsed = self.context.utils_service._parse_creative_item(raw)
                            if parsed.get("ad_id"):
                                parsed_items.append(parsed)
                    else:
                        report("warning", f"[-] Không tìm thấy quảng cáo nào trong phản hồi API của Trang {p_num}.")
                        continue
                        
                    has_youtube_to_scrape = False
                    for item in parsed_items:
                        platform = item.get("platform", "").lower()
                        media_type = item.get("media_type", "")
                        yt_url = item.get("youtube_url", "")
                        is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                        has_valid_yt = is_untruncated_youtube_url(yt_url)
                        if is_yt and not has_valid_yt:
                            has_youtube_to_scrape = True
                            break
                            
                    matched_count = 0
                    if has_youtube_to_scrape:
                        report("info", f"[*] Phát hiện quảng cáo YouTube cần lấy link trên Trang {p_num}. Bắt đầu quét và click...")
                        clicked_results = self.click_and_extract_youtube_from_page(page)
                        if clicked_results:
                            report("info", f"[+] Trích xuất được {len(clicked_results)} link YouTube từ thao tác click. Bắt đầu khớp nối...")
                            for clicked in clicked_results:
                                youtube_url = clicked.get("youtube_url")
                                clicked_ad_id = clicked.get("ad_id")
                                clicked_app_name = clicked.get("app_name") or ""
                                if not youtube_url:
                                    continue
                                matched = False
                                if clicked_ad_id:
                                    for item in parsed_items:
                                        if str(item.get("ad_id")) == str(clicked_ad_id):
                                            item["youtube_url"] = youtube_url
                                            item["media_type"] = "youtube_video"
                                            item["platform"] = "youtube"
                                            matched = True
                                            matched_count += 1
                                            report("info", f"    [✓] Khớp theo ID ({clicked_ad_id}): {youtube_url}")
                                            break
                                if matched:
                                    continue
                                res_app_clean = self.context.clean_app_name(clicked_app_name)
                                if res_app_clean:
                                    for item in parsed_items:
                                        item_app_clean = self.context.clean_app_name(item.get("app_name", ""))
                                        if item_app_clean == res_app_clean:
                                            item_platform = item.get("platform", "").lower()
                                            item_media_type = item.get("media_type", "")
                                            is_item_yt = (item_platform == "youtube" or item_media_type in ["youtube_video", "youtube_click_required"])
                                            old_url = str(item.get("youtube_url", "")).strip()
                                            if is_item_yt and (not old_url or not is_untruncated_youtube_url(old_url)):
                                                item["youtube_url"] = youtube_url
                                                item["media_type"] = "youtube_video"
                                                item["platform"] = "youtube"
                                                matched = True
                                                matched_count += 1
                                                report("info", f"    [~] Khớp theo App ({clicked_app_name} -> {item.get('app_name')}): {youtube_url}")
                                                break
                            report("info", f"[+] Hoàn tất khớp nối! Đã khớp thành công {matched_count}/{len(clicked_results)} quảng cáo YouTube.")
                        else:
                            report("warning", "[-] Không click trích xuất được link YouTube nào trên giao diện.")
                    else:
                        report("info", "[*] Trang này không có quảng cáo YouTube nào cần lấy thêm link.")
                        
                    if parsed_items:
                        append_to_csv_report(csv_path, parsed_items)
                        total_scraped += len(parsed_items)
                        total_youtube_matched += matched_count
                        pages_scraped.append(p_num)
                        report("page_success", f"[🏁] Đã lưu xong {len(parsed_items)} quảng cáo của Trang {p_num} vào: {csv_path}", extra={"page": p_num, "count": len(parsed_items)})
                except Exception as e:
                    report("error", f"[-] Lỗi trong quá trình xử lý Trang {p_num}: {e}")
            browser.close()
            
        summary = {
            "status": "success",
            "start_page": start_page,
            "end_page": end_page,
            "csv_path": csv_path,
            "total_scraped": total_scraped,
            "total_youtube_matched": total_youtube_matched,
            "pages_scraped": pages_scraped
        }
        report("complete", f"\n[🏁] Hoàn tất cào dữ liệu từ trang {start_page} đến {end_page}. File báo cáo: {csv_path}", extra={"summary": summary})
        return summary

    def run_scrape_youtube_to_csv_cli(self, argv: Optional[list] = None) -> None:
        """
        CLI để quét trang hiện tại, click trích xuất link YouTube, điền ngược vào scraped_creatives_raw.csv (nếu có)
        hoặc ghi vào file legacy scraped_youtube_links.csv.
        Tương tự logic cũ trong scrape_youtube_to_csv.py.
        """
        if not self.context:
            from socialpeta_downloader.core import SocialPetaDownloaderCore
            self.context = SocialPetaDownloaderCore(skip_db_init=True)
            
        from playwright.sync_api import sync_playwright
        from datetime import datetime
        import csv
        
        core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        modules_dir = os.path.join(core_dir, "modules")
        raw_csv_path = os.path.join(modules_dir, "scraped_creatives_raw.csv")
        
        if argv and len(argv) > 1:
            raw_csv_path = argv[1]
            
        has_raw_csv = os.path.exists(raw_csv_path)
        raw_creatives = []
        missing_youtube_count = 0
        
        if has_raw_csv:
            print(f"[+] Phát hiện file CSV thô: {raw_csv_path}")
            try:
                with open(raw_csv_path, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    raw_creatives = list(reader)
                for row in raw_creatives:
                    platform = row.get("platform", "").lower()
                    media_type = row.get("media_type", "")
                    yt_url = row.get("youtube_url", "")
                    is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                    has_valid_yt = ("youtube.com" in yt_url.lower() or "youtu.be" in yt_url.lower())
                    if is_yt and not has_valid_yt:
                        missing_youtube_count += 1
                print(f"[*] Tìm thấy {len(raw_creatives)} dòng tổng cộng, trong đó có {missing_youtube_count} quảng cáo YouTube cần điền link.")
            except Exception as e:
                print(f"[-] Lỗi khi đọc file CSV thô: {e}")
                has_raw_csv = False
                
        port = 9222
        print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
        
        if not self.context.chrome_service.ensure_chrome_debug_port(port):
            print(f"[-] LỖI: Không thể mở/kết nối tới Chrome debug port {port}.")
            return
            
        self.context.utils_service.bring_chrome_to_foreground()
        
        def save_to_csv(filepath, results):
            file_exists = os.path.exists(filepath)
            fieldnames = ["ad_id", "app_name", "youtube_url", "title", "body", "scraped_time"]
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(filepath, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                for item in results:
                    row_data = {
                        "ad_id": item.get("ad_id", ""),
                        "app_name": item.get("app_name", ""),
                        "youtube_url": item.get("youtube_url", ""),
                        "title": item.get("title", ""),
                        "body": item.get("body", ""),
                        "scraped_time": now_str
                    }
                    writer.writerow(row_data)
                    
        def overwrite_raw_csv(filepath, rows):
            fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                          "duration", "impression", "heat", "platform", "download_time",
                          "publisher", "app_name", "area", "copywriting_language", "title",
                          "body", "deployment_time", "saved_path", "file_size"]
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    clean_row = {k: row.get(k, "") for k in fieldnames}
                    writer.writerow(clean_row)
                    
        with sync_playwright() as p:
            browser, page = self.context.connect_to_active_tab(p, port)
            if not page:
                print("[-] LỖI: Không tìm thấy tab SocialPeta nào đang mở hoặc không kết nối được.")
                return
                
            try:
                current_title = page.title()
                current_url = page.url
                print("\n" + "="*80)
                print("[🎉] KẾT NỐI THÀNH CÔNG TỚI TAB:")
                print(f"    - Tiêu đề : {current_title}")
                print(f"    - URL      : {current_url}")
                print("="*80 + "\n")
                
                try:
                    page.bring_to_front()
                except Exception:
                    pass
                    
                try:
                    page_num = self.context.utils_service.get_current_page(page)
                    print(f"[+] Bạn đang ở trang thứ: {page_num}")
                except Exception as e:
                    print(f"[*] Không đọc được trang hiện tại từ giao diện UI: {e}")
                    
                print("[*] Bắt đầu quét và click từng icon YouTube trên trang để lấy link thực tế...")
                results = self.click_and_extract_youtube_from_page(page)
                
                if not results:
                    print("[-] Không tìm thấy hoặc không trích xuất được link YouTube nào từ trang hiện tại.")
                else:
                    print(f"\n[🏁] Trích xuất thành công {len(results)} đường dẫn YouTube!")
                    for idx, res in enumerate(results, 1):
                        print(f"  {idx}. ID: {res.get('ad_id')} | App: {res.get('app_name')} | URL: {res.get('youtube_url')}")
                        
                    if has_raw_csv and raw_creatives:
                        print(f"[*] Đang tiến hành khớp nối và tự điền link vào file CSV thô...")
                        updated_count = 0
                        for res in results:
                            res_ad_id = str(res.get("ad_id", "")).strip()
                            res_url = str(res.get("youtube_url", "")).strip()
                            if not res_ad_id or not res_url:
                                continue
                            matched = False
                            for row in raw_creatives:
                                row_ad_id = str(row.get("ad_id", "")).strip()
                                if row_ad_id == res_ad_id:
                                    old_url = str(row.get("youtube_url", "")).strip()
                                    if not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower()):
                                        row["youtube_url"] = res_url
                                        if row.get("media_type") == "youtube_click_required":
                                            row["media_type"] = "youtube_video"
                                        updated_count += 1
                                        matched = True
                                        print(f"  [✓] Cập nhật (khớp ID {res_ad_id}): {res_url}")
                                        break
                            if not matched:
                                res_app_clean = self.context.clean_app_name(res.get("app_name", ""))
                                if res_app_clean:
                                    for row in raw_creatives:
                                        row_app_clean = self.context.clean_app_name(row.get("app_name", ""))
                                        if row_app_clean == res_app_clean:
                                            row_platform = row.get("platform", "").lower()
                                            row_media_type = row.get("media_type", "")
                                            is_row_yt = (row_platform == "youtube" or row_media_type in ["youtube_video", "youtube_click_required"])
                                            old_url = str(row.get("youtube_url", "")).strip()
                                            if is_row_yt and (not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower())):
                                                row["youtube_url"] = res_url
                                                if row.get("media_type") == "youtube_click_required":
                                                    row["media_type"] = "youtube_video"
                                                updated_count += 1
                                                matched = True
                                                print(f"  [~] Cập nhật (khớp App '{res_app_clean}', ID {row.get('ad_id')}): {res_url}")
                                                break
                        overwrite_raw_csv(raw_csv_path, raw_creatives)
                        print(f"[🎉] Hoàn tất cập nhật file CSV thô. Đã tự điền thành công {updated_count} đường dẫn YouTube vào {raw_csv_path}")
                    else:
                        legacy_csv_path = os.path.join(modules_dir, "scraped_youtube_links.csv")
                        print(f"[*] Không có file raw CSV. Đang lưu {len(results)} dòng dữ liệu vào file legacy CSV...")
                        save_to_csv(legacy_csv_path, results)
                        print(f"[🎉] Đã lưu thành công dữ liệu vào: {legacy_csv_path}")
            except Exception as e:
                print(f"[-] Gặp lỗi khi thao tác trên tab: {e}")
            finally:
                browser.close()
                print("[*] Đã ngắt kết nối trình duyệt an toàn.")

