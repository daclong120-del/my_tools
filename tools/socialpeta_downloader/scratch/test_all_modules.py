import os
import sys
import subprocess

def print_header(title):
    print("\n" + "="*80)
    print(f" {title.center(78)} ")
    print("="*80)

def run_command(cmd, cwd=None, env=None):
    """Run command and return (stdout, stderr, returncode)"""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            encoding='utf-8',
            errors='ignore'
        )
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), -1

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # socialpeta_downloader's parent directory is the root for python path
    python_path = os.path.dirname(os.path.dirname(script_dir))
    modules_dir = os.path.join(python_path, "socialpeta_downloader", "modules")
    
    # List of 15 modules to test
    modules = [
        "clear_session",
        "click_youtube_icons",
        "connect_current_tab",
        "connect_first_tab",
        "download_images",
        "download_video_youtube_only",
        "download_videos_not_youtube",
        "filter_youtube_creatives",
        "get_current_page",
        "list_tabs",
        "page_navigation",
        "run_crawler",
        "scrape_current_page_yt",
        "scrape_pages_1_to_10_yt",
        "scrape_youtube_to_csv"
    ]
    
    report_lines = []
    report_lines.append("="*90)
    report_lines.append(f"| {'Module Name':<30} | {'Syntax/Import Check':<25} | {'Execution Test':<25} |")
    report_lines.append("="*90)
    
    print_header("STARTING TESTING FOR ALL SCRIPT MODULES")
    
    # Ensure socialpeta_downloader is in PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = python_path
    
    for mod in modules:
        print(f"[*] Checking module: {mod}...")
        script_path = os.path.join(modules_dir, f"{mod}.py")
        
        # 1. Syntax & Import Check
        import_cmd = f'python -c "import socialpeta_downloader.modules.{mod}"'
        stdout, stderr, code = run_command(import_cmd, env=env)
        
        import_status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            print(f"  [-] Import error in module {mod}:\n{stderr}")
        
        # 2. Execution Test
        exec_status = "N/A"
        
        # Select safe scripts to run a quick test
        if mod == "clear_session":
            run_cmd = f'python "{script_path}" --keep-history'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            exec_status = "PASS" if code_run == 0 else "FAIL"
            if code_run != 0:
                print(f"  [-] Execution error in clear_session:\n{stderr_run}")
                
        elif mod == "list_tabs":
            run_cmd = f'python "{script_path}"'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            exec_status = "PASS" if code_run == 0 else "FAIL"
            if code_run != 0:
                print(f"  [-] Execution error in list_tabs:\n{stderr_run}")
                
        elif mod == "get_current_page":
            run_cmd = f'python "{script_path}"'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            exec_status = "PASS" if code_run == 0 else "FAIL"
            if code_run != 0:
                print(f"  [-] Execution error in get_current_page:\n{stderr_run}")
                
        elif mod == "connect_current_tab":
            run_cmd = f'python "{script_path}"'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            exec_status = "PASS" if code_run == 0 else "FAIL"
            
        elif mod == "connect_first_tab":
            run_cmd = f'python "{script_path}"'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            exec_status = "PASS" if code_run == 0 else "FAIL"

        elif mod == "filter_youtube_creatives":
            run_cmd = f'python "{script_path}" dummy_nonexistent.csv'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            has_traceback = "Traceback" in stderr_run or "Traceback" in stdout_run
            exec_status = "PASS" if not has_traceback else "FAIL"
            if has_traceback:
                print(f"  [-] Crash in filter_youtube_creatives:\n{stderr_run or stdout_run}")
                
        elif mod == "download_video_youtube_only":
            run_cmd = f'python "{script_path}" --url invalid_url'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            has_traceback = "Traceback" in stderr_run or "Traceback" in stdout_run
            exec_status = "PASS" if not has_traceback else "FAIL"
            if has_traceback:
                print(f"  [-] Crash in download_video_youtube_only:\n{stderr_run or stdout_run}")
                
        elif mod in ["download_images", "download_videos_not_youtube"]:
            run_cmd = f'python "{script_path}" dummy_nonexistent.csv'
            stdout_run, stderr_run, code_run = run_command(run_cmd, env=env)
            has_traceback = "Traceback" in stderr_run or "Traceback" in stdout_run
            exec_status = "PASS" if not has_traceback else "FAIL"
            if has_traceback:
                print(f"  [-] Crash in media download module:\n{stderr_run or stdout_run}")
                
        report_lines.append(f"| {mod:<30} | {import_status:<25} | {exec_status:<25} |")

    report_lines.append("="*90)
    
    # Save report to test_report.txt
    report_text = "\n".join(report_lines)
    report_path = os.path.join(script_dir, "test_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    print_header("TEST RESULTS DETAILED")
    print(report_text)
    print(f"\nSaved test report to: {report_path}")

if __name__ == "__main__":
    main()
