import psutil
import os

def kill_workspace_processes():
    root_dir = r"D:\Python\my_tools"
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            exe = proc.info.get('exe')
            if exe and exe.lower().startswith(root_dir.lower()):
                # Avoid killing current python process
                if proc.info.get('pid') == os.getpid():
                    continue
                print(f"Killing process {proc.info.get('pid')} ({proc.info.get('name')}) running from workspace")
                proc.kill()
                killed += 1
        except Exception:
            continue
    print(f"Killed {killed} workspace process(es).")

if __name__ == '__main__':
    kill_workspace_processes()
