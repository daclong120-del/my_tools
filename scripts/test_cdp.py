import time
import uuid
import traceback
from playwright.sync_api import sync_playwright

def test_cdp():
    out_lines = []
    out_lines.append("[*] Connecting to Chrome via CDP on port 9222...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=5000)
            out_lines.append(f"[+] Connected! Contexts count: {len(browser.contexts)}")
            if not browser.contexts:
                return
            context = browser.contexts[0]
            out_lines.append(f"[+] Pages count: {len(context.pages)}")
            for idx, page in enumerate(context.pages):
                try:
                    url = page.url
                    title = page.title()
                    out_lines.append(f"  Tab {idx}: Title='{title}', URL='{url}'")
                    
                    # Try to get window.__tab_id
                    tab_id = None
                    try:
                        tab_id = page.evaluate("window.__tab_id")
                        out_lines.append(f"    - page.evaluate('window.__tab_id') returned: {tab_id}")
                    except Exception as e_eval1:
                        tb = traceback.format_exc()
                        out_lines.append(f"    - Error page.evaluate('window.__tab_id'): {e_eval1}\n{tb}")
                        
                    if not tab_id:
                        tab_id = f"tab_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
                        try:
                            page.evaluate(f"window.__tab_id = '{tab_id}'")
                            out_lines.append(f"    - Assigned new tab_id = {tab_id} successfully")
                        except Exception as e_eval2:
                            tb = traceback.format_exc()
                            out_lines.append(f"    - Error page.evaluate(window.__tab_id = ...): {e_eval2}\n{tb}")
                except Exception as e:
                    tb = traceback.format_exc()
                    out_lines.append(f"  Tab {idx}: Outer Error: {e}\n{tb}")
    except Exception as e:
        tb = traceback.format_exc()
        out_lines.append(f"[-] Error: {e}\n{tb}")
        
    with open("test_cdp_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("[*] Wrote results to test_cdp_output.txt")

if __name__ == '__main__':
    test_cdp()
