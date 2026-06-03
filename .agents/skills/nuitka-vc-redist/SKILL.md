---
name: nuitka-vc-redist
description: "Use when debugging or fixing compiled standalone Python builds (Nuitka, PyInstaller) that fail to run on other machines due to missing DLLs or ImportError LoadLibraryExW (e.g. greenlet _greenlet.pyd failed)."
category: packaging
triggers:
  - LoadLibraryExW failed
  - ImportError: DLL load failed
  - The specified module could not be found
  - Nuitka standalone missing DLL
  - greenlet _greenlet.pyd
date_added: "2026-06-03"
---

# Nuitka VC++ Redistributable Bundling

Guide for diagnosing and bundling Microsoft Visual C++ (MSVC) Redistributable runtime DLLs into standalone Python builds (specifically Nuitka or PyInstaller) to ensure portability on fresh/clean Windows machines.

## When to Use
- A standalone compiled binary (e.g. `.exe` compiled with Nuitka `--standalone` or `--onefile`) works on the build machine but crashes instantly or throws an `ImportError` on client machines.
- Running the binary in Command Prompt (`cmd.exe`) shows an error like:
  ```
  ImportError: LoadLibraryExW '...\<package>\<extension>.pyd' failed: The specified module could not be found.
  ```
- Common packages that trigger this issue: `greenlet`, `playwright`, `cryptography`, `numpy`, `scipy`, `pandas`, `lxml` (any package compiled with C/C++ extensions).

## Root Cause
Nuitka's standalone builder automatically copies basic C runtimes like `vcruntime140.dll` and `vcruntime140_1.dll` to the distribution folder. However, it often fails to copy the **C++ Standard Library** files (`msvcp140.dll` and its variants).
When a C++ compiled `.pyd` or `.dll` in a subdirectory (e.g. `greenlet\_greenlet.pyd`) is loaded on a clean Windows machine (like Windows Sandbox, Windows Defender Application Guard, or a fresh OS install) where the system-wide VC++ Redistributable is not installed, the OS loader fails to locate `msvcp140.dll` and terminates the process with "The specified module could not be found".

## Diagnostic Steps
1. On the target machine, open **Command Prompt** (do not double-click the `.exe` directly).
2. Run the application from the prompt to capture the crash logs.
3. If it outputs `ImportError: LoadLibraryExW ... failed: The specified module could not be found.`, verify if `msvcp140.dll` is present in the distribution folder.

## How to Fix (Bundling DLLs)

To guarantee portability without requiring the end-user to install Microsoft Visual C++ Redistributable, copy the following runtime DLLs from the build machine's `C:\Windows\System32` directory directly into the root folder of your standalone build (`dist` directory):

### 1. Crucial C++ Standard Library Files
- `C:\Windows\System32\msvcp140.dll`
- `C:\Windows\System32\msvcp140_1.dll`
- `C:\Windows\System32\msvcp140_2.dll`
- `C:\Windows\System32\msvcp140_atomic_wait.dll`
- `C:\Windows\System32\msvcp140_codecvt_ids.dll`

### 2. Thread Support
- `C:\Windows\System32\vcruntime140_threads.dll`

---

## Automation in Build Scripts (Batch File Example)

In corporate deployment environments or distribution packages, automate this in your `.bat` build script:

```batch
@echo off
set "DIST_DIR=build\MyApplication"

:: 1. Run Nuitka standalone build
python -m nuitka --standalone --output-dir=build main.py

:: 2. Copy MSVC C++ Redistributable DLLs to the distribution folder root
echo [*] Copying MSVC C++ Redistributable DLLs...
copy /Y "C:\Windows\System32\msvcp140.dll" "%DIST_DIR%\msvcp140.dll"
copy /Y "C:\Windows\System32\msvcp140_1.dll" "%DIST_DIR%\msvcp140_1.dll"
copy /Y "C:\Windows\System32\msvcp140_2.dll" "%DIST_DIR%\msvcp140_2.dll"
copy /Y "C:\Windows\System32\msvcp140_atomic_wait.dll" "%DIST_DIR%\msvcp140_atomic_wait.dll"
copy /Y "C:\Windows\System32\msvcp140_codecvt_ids.dll" "%DIST_DIR%\msvcp140_codecvt_ids.dll"
copy /Y "C:\Windows\System32\vcruntime140_threads.dll" "%DIST_DIR%\vcruntime140_threads.dll"

echo [*] Portability DLLs bundled successfully!
```

Windows DLL search order ensures that when `_greenlet.pyd` or other extensions load, Windows looks in the directory of the parent process executable (`main.exe`) first and loads these local runtime DLLs.
