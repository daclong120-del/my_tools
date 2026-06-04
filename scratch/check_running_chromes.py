# scratch/check_running_chromes.py
import psutil

def check():
    print("=== RUNNING CHROME PROCESSES ===")
    count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and 'chrome' in name.lower():
                cmdline = proc.info['cmdline']
                print(f"PID {proc.info['pid']}: {name}")
                if cmdline:
                    print(f"  Cmdline: {' '.join(cmdline)}")
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    print(f"Total Chrome processes found: {count}")

if __name__ == "__main__":
    check()
