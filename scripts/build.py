import os
import sys
import shutil
import subprocess

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[*] Project root directory: {root_dir}")
    
    # 1. Build Next.js frontend
    frontend_dir = os.path.join(root_dir, "frontends", "socialpeta_downloader")
    print(f"[*] Building Next.js frontend in {frontend_dir}...")
    try:
        # On Windows, shell=True is needed to resolve npm command correctly
        subprocess.run("npm run build", shell=True, cwd=frontend_dir, check=True)
        print("[+] Frontend built successfully.")
    except Exception as e:
        print(f"[-] Failed to build frontend: {e}")
        sys.exit(1)
        
    # 2. Compile Python backend with PyInstaller
    print("[*] Compiling Python backend with PyInstaller...")
    # Add uvicorn and other hidden imports for FastAPI so the compiled exe runs without missing packages
    hidden_imports = [
        "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
        "anyio", "fastapi", "pydantic", "typing_extensions", "websockets"
    ]
    
    if sys.platform == "win32":
        pyinstaller_path = os.path.join(root_dir, ".venv", "Scripts", "pyinstaller.exe")
    else:
        pyinstaller_path = os.path.join(root_dir, ".venv", "bin", "pyinstaller")
        
    if not os.path.exists(pyinstaller_path):
        pyinstaller_path = "pyinstaller"  # Fallback to system pyinstaller if not in .venv
        
    cmd_args = [
        pyinstaller_path,
        "--clean", "-y", "--onefile",
        "--name", "api",
        "--distpath", os.path.join(root_dir, "dist"),
        "--workpath", os.path.join(root_dir, "build"),
    ]
    for imp in hidden_imports:
        cmd_args.extend(["--hidden-import", imp])
        
    cmd_args.append(os.path.join(root_dir, "tools", "socialpeta_downloader", "api.py"))
    
    # Run PyInstaller with PYTHONPATH pointing to 'tools' so it resolves imports
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(root_dir, "tools")
    
    print(f"[*] Command: {' '.join(cmd_args)}")
    try:
        subprocess.run(cmd_args, env=env, check=True)
        print("[+] Python backend compiled successfully.")
    except Exception as e:
        print(f"[-] Failed to compile backend: {e}")
        sys.exit(1)

    # 3. Copy outputs to Electron structure
    electron_dir = os.path.join(root_dir, "electron")
    electron_resources = os.path.join(electron_dir, "resources")
    electron_frontend = os.path.join(electron_dir, "frontend")
    
    os.makedirs(electron_resources, exist_ok=True)
    
    # Copy api binary
    exe_name = "api.exe" if sys.platform == "win32" else "api"
    src_exe = os.path.join(root_dir, "dist", exe_name)
    dst_exe = os.path.join(electron_resources, exe_name)
    print(f"[*] Copying {src_exe} to {dst_exe}...")
    shutil.copy2(src_exe, dst_exe)
    
    # Copy frontend static files
    src_out = os.path.join(frontend_dir, "out")
    print(f"[*] Copying {src_out} to {electron_frontend}...")
    if os.path.exists(electron_frontend):
        shutil.rmtree(electron_frontend)
    shutil.copytree(src_out, electron_frontend)
    
    # 4. Package Electron App
    print("[*] Packaging Electron app...")
    try:
        subprocess.run("npm run dist", shell=True, cwd=electron_dir, check=True)
        print("[+] Electron app packaged successfully!")
    except Exception as e:
        print(f"[-] Failed to package Electron app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
