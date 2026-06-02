import os
import ast
import sys

def get_stdlib_modules():
    if hasattr(sys, 'stdlib_module_names'):
        return sys.stdlib_module_names
    # Fallback list for older Python versions
    return {
        'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections', 'configparser',
        'contextlib', 'copy', 'csv', 'datetime', 'email', 'fnmatch', 'functools',
        'hashlib', 'html', 'http', 'importlib', 'inspect', 'io', 'json', 'logging',
        'math', 'multiprocessing', 'os', 'pathlib', 'pickle', 'pprint', 'queue',
        're', 'select', 'shutil', 'signal', 'socket', 'sqlite3', 'ssl', 'string',
        'subprocess', 'sys', 'tempfile', 'threading', 'time', 'traceback', 'types',
        'typing', 'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zipfile', 'zlib'
    }

def scan_imports(directory):
    imports = set()
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        node = ast.parse(f.read(), filename=path)
                    for child in ast.walk(node):
                        if isinstance(child, ast.Import):
                            for name in child.names:
                                imports.add(name.name.split('.')[0])
                        elif isinstance(child, ast.ImportFrom):
                            if child.level is None or child.level == 0:
                                if child.module:
                                    imports.add(child.module.split('.')[0])
                except Exception as e:
                    print(f"Error parsing {path}: {e}")
    return imports

def read_requirements(filepath):
    reqs = set()
    if not os.path.exists(filepath):
        return reqs
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Parse package name, stripping version specifiers
            name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].strip()
            # Normalize name
            name = name.replace('-', '_').lower()
            reqs.add(name)
    return reqs

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools_dir = os.path.join(root_dir, "tools", "socialpeta_downloader")
    req_file = os.path.join(root_dir, "requirements.txt")
    
    print(f"Scanning imports in: {tools_dir}")
    all_imports = scan_imports(tools_dir)
    
    stdlib = get_stdlib_modules()
    
    # Filter out stdlib and internal project modules
    third_party_imports = set()
    for imp in all_imports:
        imp_lower = imp.lower()
        if imp_lower in stdlib or imp_lower == "socialpeta_downloader":
            continue
        third_party_imports.add(imp_lower)
        
    print(f"Detected third-party imports: {third_party_imports}")
    
    requirements = read_requirements(req_file)
    print(f"Requirements.txt packages: {requirements}")
    
    missing = third_party_imports - requirements
    # uvicorn is often run but not imported directly in code, it should be in reqs
    # python-multipart is required by fastapi for forms
    # websockets is uvicorn's dependency
    special_packages = {"uvicorn", "websockets", "wsproto", "python_multipart", "anyio"}
    
    print("\n--- AUDIT RESULTS ---")
    print(f"Missing from requirements.txt: {missing}")
    
    # Check if any special packages are missing from requirements.txt
    missing_special = special_packages - requirements
    if missing_special:
        print(f"Missing crucial hidden dependencies: {missing_special}")
        
    extra = requirements - third_party_imports - special_packages
    print(f"Extra in requirements.txt (not directly imported): {extra}")

if __name__ == "__main__":
    main()
