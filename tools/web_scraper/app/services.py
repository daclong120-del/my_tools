import requests
from bs4 import BeautifulSoup
import urllib.parse

class WebScraperService:
    @staticmethod
    def scrape_url(url: str) -> dict:
        # Validate URL schema
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("URL khong hop le. Can phai bat dau bang http:// hoac https://")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Lay tieu de trang
        title = soup.title.string.strip() if soup.title else ""
        
        # Lay cac the heading
        headings = {}
        for h_tag in ['h1', 'h2', 'h3']:
            headings[h_tag] = [h.get_text().strip() for h in soup.find_all(h_tag) if h.get_text().strip()]
            
        # Lay description meta tag
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc.get('content').strip()
            
        # Lay snippet text (lay 500 ky tu dau tien tu body)
        body_text = ""
        if soup.body:
            # Clear script and style elements
            for script in soup.body(["script", "style"]):
                script.decompose()
            body_text = " ".join(soup.body.get_text().split())[:500] + "..."
            
        return {
            "status": "success",
            "url": url,
            "title": title,
            "description": description,
            "headings": headings,
            "snippet": body_text
        }
