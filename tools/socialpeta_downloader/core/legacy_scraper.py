# tools/socialpeta_downloader/core/legacy_scraper.py
"""
Responsibility: Legacy search page scraper and single ad downloader methods.
"""

import os
import re
import csv
import time
import requests
from datetime import datetime
from typing import Optional, Any
from playwright.sync_api import sync_playwright
from socialpeta_downloader.config import settings
from socialpeta_downloader.core.protocols import IEngineContext

class LegacyScraperService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def is_safe_url(self, url: str) -> bool:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            if parsed.scheme != "https":
                return False
            domain = parsed.netloc.lower()
            if domain == "socialpeta.com" or domain.endswith(".socialpeta.com"):
                return True
            if domain == "guangdada.com" or domain.endswith(".guangdada.com"):
                return True
        except Exception:
            pass
        return False

    def download_video_file(self, url: str, dest_path: str) -> bool:
        if not self.context:
            return False
            
        basename = os.path.basename(dest_path)
        self.context.utils_service.log("info", f"Bắt đầu tải file: {basename} ...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.socialpeta.com/"
        }
        for attempt in range(4):
            try:
                response = requests.get(url, headers=headers, stream=True, timeout=20)
                if response.status_code == 200:
                    with open(dest_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=16384):
                            if chunk:
                                f.write(chunk)
                    self.context.utils_service.log("success", f"Đã tải thành công file: {basename}")
                    return True
                time.sleep(2 ** attempt)
            except Exception as e:
                self.context.utils_service.log("warning", f"Lỗi tải file {basename} (lần thử {attempt+1}): {e}")
                time.sleep(2 ** attempt)
        self.context.utils_service.log("error", f"Tải file thất bại sau 4 lần thử: {basename}")
        return False

    def download_single_ad(self, url: str) -> dict:
        if not self.context:
            return {}
            
        print(f"[*] Dang tai single ad tu URL: {url}")
        ad_id = self.context.utils_service.extract_ad_id(url) or "unknown"
        result = {
            "ad_id": ad_id,
            "ad_url": url,
            "video_url": None,
            "title": "",
            "saved_path": None,
            "status": "failed",
            "error": None
        }
        
        if not self.is_safe_url(url):
            result["error"] = "URL không hợp lệ. Chỉ chấp nhận các trang thuộc socialpeta.com hoặc guangdada.com."
            return result
            
        with sync_playwright() as p:
            try:
                context = self.context.utils_service._get_playwright_context(p)
                page = context.pages[0] if context.pages else context.new_page()
                
                video_url_found = []
                def on_resp(response):
                    if "/creative/detail" in response.url or "/creative/get" in response.url:
                        try:
                            res_json = response.json()
                            data = res_json.get("data", {})
                            if isinstance(data, dict):
                                video_url = data.get("video_url") or data.get("video") or data.get("url")
                                if video_url:
                                    video_url_found.append(video_url)
                        except Exception:
                            pass
                            
                page.on("response", on_resp)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
                
                video_el = page.locator("video").first
                video_url = None
                if video_el.count() > 0:
                    video_url = video_el.get_attribute("src")
                    
                if not video_url and video_url_found:
                    video_url = video_url_found[0]
                    
                title = ""
                try:
                    title_el = page.locator("h1, .ad-title, .title").first
                    if title_el.count() > 0:
                        title = title_el.inner_text().strip()
                except Exception:
                    pass
                
                result["title"] = title
                
                if video_url:
                    result["video_url"] = video_url
                    app_name = title or "SingleAd"
                    final_filename, stt = self.context.utils_service.get_unique_filename(app_name)
                    final_path = os.path.join(self.context.download_dir, final_filename)
                    
                    dl_ok = self.download_video_file(video_url, final_path)
                    if dl_ok:
                        result["saved_path"] = final_path
                        result["status"] = "success"
                    else:
                        result["error"] = "Không thể tải file video từ CDN URL."
                else:
                    iframe_el = page.locator("iframe[src*='youtube']").first
                    if iframe_el.count() > 0:
                        iframe_src = iframe_el.get_attribute("src")
                        result["video_url"] = iframe_src
                        result["error"] = "Video YouTube không hỗ trợ tải trực tiếp. Vui lòng sử dụng tính năng Concurrent Crawler để tự động click lấy iframe."
                    else:
                        result["error"] = "Không tìm thấy video link hoặc video tag."
                        
                context.close()
            except Exception as e:
                result["error"] = f"Lỗi Playwright: {str(e)}"
                
        return result

    def scrape_search_page_and_download(self, url: str, max_results: int = 10) -> list:
        if not self.context:
            return []
            
        print(f"[*] Dang quet trang tim kiem: {url} (Gioi han: {max_results})")
        results = []
        if not self.is_safe_url(url):
            print(f"[-] URL không hợp lệ: {url}")
            return results
        captured_items = []
        
        with sync_playwright() as p:
            try:
                context = self.context.utils_service._get_playwright_context(p)
                page = context.pages[0] if context.pages else context.new_page()
                
                def on_resp(response):
                    if "/creative/list" in response.url or "/creative-rank/list" in response.url:
                        try:
                            body = response.json()
                            items = self.context.utils_service._recursive_find_creatives(body)
                            for raw_item in items:
                                parsed = self.context.utils_service._parse_creative_item(raw_item)
                                if parsed["ad_id"] and parsed not in captured_items:
                                    captured_items.append(parsed)
                        except Exception:
                            pass
                            
                page.on("response", on_resp)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                for scroll in range(5):
                    if len(captured_items) >= max_results:
                        break
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(3)
                    
                context.close()
            except Exception as e:
                print(f"[-] scrape_search_page_and_download error: {e}")
                
        items_to_download = captured_items[:max_results]
        print(f"[+] Da quet duoc {len(items_to_download)} ads de tai.")
        
        for item in items_to_download:
            ad_id = item["ad_id"]
            video_url = item["video_url"]
            title = item.get("app_name") or "AdVideo"
            
            res_dict = {
                "ad_id": ad_id,
                "ad_url": f"https://ads.socialpeta.com/creative/detail?id={ad_id}" if "http" not in item.get("ad_url", "") else item["ad_url"],
                "video_url": video_url,
                "title": title,
                "saved_path": None,
                "status": "failed",
                "error": None
            }
            
            if not video_url:
                res_dict["error"] = "Không có link tải trực tiếp (có thể là YouTube hidden link)."
                results.append(res_dict)
                continue
                
            final_filename, stt = self.context.utils_service.get_unique_filename(title)
            final_path = os.path.join(self.context.download_dir, final_filename)
            
            dl_ok = self.download_video_file(video_url, final_path)
            if dl_ok:
                res_dict["saved_path"] = final_path
                res_dict["status"] = "success"
                item_state = {
                    "ad_id": ad_id,
                    "app_name": title,
                    "video_url": video_url,
                    "ad_url": res_dict["ad_url"],
                    "youtube_url": "",
                    "status": "done",
                    "saved_path": final_path,
                    "file_size": os.path.getsize(final_path) if os.path.exists(final_path) else 0
                }
                self.context.utils_service._save_item_state(item_state)
                self.context.session_service.append_to_csv(item_state)
            else:
                res_dict["error"] = "Tải file video CDN thất bại."
                
            results.append(res_dict)
            
        return results
