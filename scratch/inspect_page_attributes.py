import sys
import os
from playwright.sync_api import sync_playwright

def main():
    port = 9222
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=2000)
            context = browser.contexts[0]
            for idx, page in enumerate(context.pages):
                print(f"\nPage #{idx}:")
                # Print all attributes of page
                attrs = dir(page)
                print(f"  Public attributes: {[a for a in attrs if not a.startswith('_')]}")
                
                # Check _impl
                if hasattr(page, "_impl"):
                    impl = page._impl
                    impl_attrs = dir(impl)
                    print(f"  _impl attributes: {[a for a in impl_attrs if not a.startswith('_')]}")
                    
                    # Look for anything containing 'target' or 'id'
                    target_related = [a for a in impl_attrs if 'target' in a.lower() or 'id' in a.lower()]
                    print(f"  Target/ID related attributes: {target_related}")
                    
                    # If there's a target, print its attributes
                    if hasattr(impl, "target"):
                        print(f"  impl.target type: {type(impl.target)}")
                        print(f"  impl.target attributes: {dir(impl.target)}")
                        
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
