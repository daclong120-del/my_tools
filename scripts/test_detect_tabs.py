import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore()
    print("[*] Running core.detect_tabs()...")
    tabs = core.detect_tabs()
    print(f"[+] Returned tabs count: {len(tabs)}")
    print(f"[+] Tabs: {tabs}")
    print(f"[+] Tab states: {core.tab_states}")

if __name__ == '__main__':
    main()
