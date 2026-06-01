import psutil

def kill_debug_chrome():
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and name.lower() == 'chrome.exe':
                cmdline = proc.info['cmdline']
                if cmdline and any('chrome_debug_profile' in part for part in cmdline):
                    print(f"Killing Chrome process {proc.info['pid']} using debug profile")
                    proc.kill()
                    killed += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    print(f"Killed {killed} debug Chrome process(es).")

if __name__ == '__main__':
    kill_debug_chrome()
