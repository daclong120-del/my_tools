# tools/socialpeta_downloader/scratch/test_cli_scenarios.py
import subprocess
import sys
import os

def run_command(args):
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "new_cli.py")
    cmd = [python_exe, script_path] + args
    print(f"[*] Running command: {' '.join(cmd)}")
    
    # Set PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="ignore")
    return res

def test_help():
    print("\n--- Test scenario: help ---")
    res = run_command(["--help"])
    assert res.returncode == 0
    assert "Unified CLI Tool" in res.stdout
    print("[+] PASS: --help works correctly.")

def test_subcommands():
    # Test invalid command
    print("\n--- Test scenario: invalid subcommand ---")
    res = run_command(["invalid_cmd"])
    assert res.returncode != 0
    print("[+] PASS: invalid command handled correctly.")

    # Test list-tabs (without running Chrome, should return list or check output)
    print("\n--- Test scenario: list-tabs ---")
    res = run_command(["list-tabs"])
    # May have zero exit code or not depending on active Chrome, but shouldn't raise Python exception
    assert "Traceback" not in res.stderr and "Traceback" not in res.stdout
    print("[+] PASS: list-tabs run successfully (no python traceback).")

    # Test connect-tab
    print("\n--- Test scenario: connect-tab ---")
    res = run_command(["connect-tab"])
    assert "Traceback" not in res.stderr and "Traceback" not in res.stdout
    print("[+] PASS: connect-tab run successfully (no python traceback).")

    # Test clear
    print("\n--- Test scenario: clear --keep-history ---")
    res = run_command(["clear", "--keep-history"])
    assert "Traceback" not in res.stderr and "Traceback" not in res.stdout
    print("[+] PASS: clear run successfully.")

if __name__ == "__main__":
    print("==================================================")
    print("       RUNNING SCRATCH INTEGRATION CLI TESTS      ")
    print("==================================================")
    try:
        test_help()
        test_subcommands()
        print("\n[+] ALL CLI SUBCOMMAND TESTS COMPLETED SUCCESSFULLY!")
    except AssertionError as e:
        print(f"\n[-] TEST FAILURE: {e}")
        sys.exit(1)
