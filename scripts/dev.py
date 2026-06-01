import subprocess
import sys
import time
import os

def run_backend(name, path, port):
    print(f"[*] Dang khoi dong {name} tai cong {port}...")
    
    # Path to main.py
    main_file = os.path.join(path, "app", "main.py")
    
    # Run uvicorn server in a subprocess
    # We use sys.executable to ensure we use the same Python environment
    cmd = [sys.executable, main_file]
    
    # Set environment variables for specific ports
    env = os.environ.copy()
    
    # Start process
    # Cwd set to the specific backend folder so imports inside it resolve correctly
    process = subprocess.Popen(
        cmd,
        cwd=path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    return process

def monitor_process(name, process):
    # Non-blocking print of logs from subprocess
    # We do a quick check
    try:
        # Read available lines without blocking
        # Since standard Popen.stdout.readline can block, we can just print that it started
        # In a real environment, we'd read logs asynchronously, but to keep it simple,
        # we will let uvicorn output to console directly or write to a file,
        # or we can simply forward stdout/stderr by omitting stdout/stderr arguments.
        pass
    except Exception as e:
        print(f"Loi doc log tu {name}: {e}")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools_dir = os.path.join(base_dir, "tools")
    
    invoice_parser_path = os.path.join(tools_dir, "invoice_parser")
    web_scraper_path = os.path.join(tools_dir, "web_scraper")
    socialpeta_path = os.path.join(tools_dir, "socialpeta_downloader")
    
    processes = {}
    
    try:
        # Khoi dong cac backend, cho phep output in ra man hinh truc tiep
        print("[*] Khoi dong cac dich vu tools...")
        
        # invoice_parser (port 8001)
        invoice_proc = subprocess.Popen(
            [sys.executable, "-m", "invoice_parser.api"],
            cwd=tools_dir
        )
        processes["invoice_parser"] = invoice_proc
        
        # web_scraper (port 8002)
        scraper_proc = subprocess.Popen(
            [sys.executable, "-m", "app.main"],
            cwd=web_scraper_path
        )
        processes["web_scraper"] = scraper_proc
        
        # socialpeta_downloader (port 8003)
        socialpeta_proc = subprocess.Popen(
            [sys.executable, "-m", "socialpeta_downloader.api"],
            cwd=tools_dir
        )
        processes["socialpeta_downloader"] = socialpeta_proc
        
        print("\n[+] Ca 3 backend dang chay!")
        print("  -> Invoice Parser API: http://127.0.0.1:8001")
        print("  -> Web Scraper API:    http://127.0.0.1:8002")
        print("  -> SocialPeta API:     http://127.0.0.1:8003")
        print("Nhan Ctrl+C de dung tat ca cac dich vu.\n")
        
        # Vong lap vo han de theo doi cac tien trinh
        while True:
            for name, proc in list(processes.items()):
                poll = proc.poll()
                if poll is not None:
                    print(f"[!] Tien trinh {name} da dung voi code {poll}")
                    del processes[name]
            
            if not processes:
                print("[-] Khong con dich vu nao hoat dong.")
                break
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[-] Nhan Ctrl+C. Dang dung tat ca cac backend...")
    finally:
        # Dung tat ca cac tien trinh con
        for name, proc in processes.items():
            if proc.poll() is None:
                print(f"[*] Dang tat {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[+] Hoan thanh dung cac backend.")

if __name__ == "__main__":
    main()
