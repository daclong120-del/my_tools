import threading
import time
import psutil

class SystemMonitor:
    def __init__(self, ram_threshold=93.0, cpu_threshold=90.0, check_interval=2.0, max_threads_user=8):
        self.ram_threshold = ram_threshold
        self.cpu_threshold = cpu_threshold
        self.check_interval = check_interval
        self.max_threads_user = max_threads_user
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Get total system memory in GB
        total_mem = psutil.virtual_memory().total / (1024 ** 3)
        self.low_ram_system = total_mem < 4.0
        
        # Thread status properties
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.is_ram_critical = False
        self.is_cpu_critical = False
        
        # UC-09c: Low RAM capped at 2 threads
        if self.low_ram_system:
            self.max_threads_recommended = 2
            print(f"[*] Canh bao: He thong co RAM thap ({total_mem:.2f}GB < 4GB). Gioi han toi da 2 luong tai.")
        else:
            self.max_threads_recommended = max_threads_user
            
        self.cpu_critical_duration = 0.0
        self.running = False
        self.monitor_thread = None

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()

    def stop(self):
        with self.lock:
            self.running = False

    def _monitor_loop(self):
        while self.running:
            try:
                # Get CPU percentage (non-blocking call since we run in loop)
                cpu = psutil.cpu_percent()
                # Get RAM percentage
                ram = psutil.virtual_memory().percent
                
                with self.lock:
                    self.cpu_usage = cpu
                    self.ram_usage = ram
                    
                    # UC-09a: RAM limit checks
                    self.is_ram_critical = ram > self.ram_threshold
                    
                    # UC-09b: CPU limit checks (>90% sustained)
                    if cpu > self.cpu_threshold:
                        self.cpu_critical_duration += self.check_interval
                    else:
                        self.cpu_critical_duration = 0.0
                        
                    self.is_cpu_critical = self.cpu_critical_duration >= 10.0
                    
                    # Dynamic thread limit adjustments based on resource usage
                    if self.low_ram_system:
                        self.max_threads_recommended = 2
                    elif self.is_ram_critical:
                        # Seriously degrade to 1 thread if memory is critical to prevent OOM
                        self.max_threads_recommended = 1
                    elif self.is_cpu_critical:
                        # Throttle down if CPU is overloaded
                        self.max_threads_recommended = max(2, self.max_threads_recommended - 1)
                    else:
                        # Recover recommendation up to max_threads_user if system is healthy
                        self.max_threads_recommended = min(self.max_threads_user, self.max_threads_recommended + 1)
                        
            except Exception as e:
                print(f"[-] Loi trong luong giam sat he thong: {e}")
                
            time.sleep(self.check_interval)

    def get_stats(self):
        with self.lock:
            return {
                "cpu_usage": self.cpu_usage,
                "ram_usage": self.ram_usage,
                "is_ram_critical": self.is_ram_critical,
                "is_cpu_critical": self.is_cpu_critical,
                "max_threads_recommended": self.max_threads_recommended,
                "low_ram_system": self.low_ram_system
            }
