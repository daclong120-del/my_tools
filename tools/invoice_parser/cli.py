import argparse
import sys
import os
import json

# Setup import path if run directly
# This allows running 'python cli.py' directly from within the folder, or 'python -m invoice_parser.cli'
if __name__ == "__main__" and __package__ is None:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(parent_dir)

from invoice_parser.core import InvoiceParserCore
from invoice_parser.agent import InvoiceAgent
from invoice_parser.config import settings

def handle_parse(args):
    print(f"[*] Dang parse file hoa don: {args.file_path}")
    core = InvoiceParserCore()
    try:
        data = core.process_invoice_from_path(args.file_path, sync_external=args.sync)
        print("\n[+] Trich xuat du lieu thanh cong:")
        print(json.dumps(data.model_dump(), indent=4, ensure_ascii=False))
        
        if args.audit:
            print("\n[*] Dang chay audit kiem tra loi bang Agent...")
            agent = InvoiceAgent()
            is_valid, warnings = agent.run_agent_audit(data)
            if is_valid:
                print("[+] Hoa don hop le! Khong phat hien bat thuong.")
            else:
                print("[-] Canh bao bat thuong tren hoa don:")
                for w in warnings:
                    print(f"  - {w}")
    except Exception as e:
        print(f"[!] Loi: {e}", file=sys.stderr)
        sys.exit(1)

def handle_server(args):
    print(f"[*] Dang khoi dong FastAPI server tren {args.host}:{args.port}...")
    import uvicorn
    # Phai chay qua module namespace de reload hoat dong dung
    uvicorn.run("invoice_parser.api:app", host=args.host, port=args.port, reload=args.reload)

def interactive_menu():
    # ANSI escape colors
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    
    while True:
        # Clear screen on Windows or Unix
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f"{MAGENTA}{BOLD}   GIAO DIEN TUONG TAC TERMINAL - INVOICE PARSER   {RESET}")
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f" {GREEN}[1]{RESET} Trich xuat (Parse) hoa don tu file")
        print(f" {GREEN}[2]{RESET} Khoi chay API Server (FastAPI)")
        print(f" {GREEN}[3]{RESET} Thoat chuong trinh")
        print(f"{CYAN}--------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Nhap lua chon cua ban (1-3): {RESET}").strip()
        
        if choice == "1":
            print(f"\n{YELLOW}==> Huong dan: Keo & tha file cua ban vao day hoac nhap duong dan.{RESET}")
            file_path = input(f"{BOLD}Duong dan file hoa don: {RESET}").strip()
            # remove quotes in case of drag & drop
            file_path = file_path.strip("\"'")
            
            if not file_path:
                input(f"\n{YELLOW}Duong dan trong. Nhan Enter de tiep tuc...{RESET}")
                continue
                
            if not os.path.exists(file_path):
                print(f"\n[!] File khong ton tai: {file_path}")
                input(f"\n{YELLOW}Nhan Enter de tiep tuc...{RESET}")
                continue
            
            sync_opt = input(f"{BOLD}Dong bo du lieu sang phan mem ke toan? (y/N): {RESET}").strip().lower()
            sync = sync_opt in ("y", "yes")
            
            audit_opt = input(f"{BOLD}Chay Agent kiem tra loi/sai sot hoa don? (Y/n): {RESET}").strip().lower()
            audit = audit_opt not in ("n", "no")
            
            print(f"\n{CYAN}[*] Bat dau xu ly...{RESET}")
            class Args:
                file_path = file_path
                sync = sync
                audit = audit
            handle_parse(Args)
            input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
            
        elif choice == "2":
            print(f"\n{CYAN}[*] Khoi chay API server...{RESET}")
            class Args:
                host = settings.HOST
                port = settings.API_PORT
                reload = True
            try:
                handle_server(Args)
            except KeyboardInterrupt:
                print(f"\n{YELLOW}[*] Da dung API server.{RESET}")
                input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
                
        elif choice == "3":
            print(f"\n{GREEN}Cam on ban da su dung Invoice Parser! Tam biet.{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n[!] Lua chon khong hop le.")
            input(f"\n{YELLOW}Nhan Enter de tiep tuc...{RESET}")

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        description="Invoice Parser Command Line Interface (CLI)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Cac lenh hoat dong")
    subparsers.required = True

    # 1. Subcommand: parse
    parse_parser = subparsers.add_parser("parse", help="Parse mot file hoa don")
    parse_parser.add_argument("file_path", type=str, help="Duong dan den file hoa don (PDF, Image...)")
    parse_parser.add_argument("--sync", action="store_true", help="Dong bo sang he thong ke toan")
    parse_parser.add_argument("--audit", action="store_true", help="Tu dong chay audit kiem tra sai sot")
    parse_parser.set_defaults(func=handle_parse)

    # 2. Subcommand: server
    server_parser = subparsers.add_parser("server", help="Khoi chay API server FastAPI")
    server_parser.add_argument("--host", type=str, default=settings.HOST, help="IP Host")
    server_parser.add_argument("--port", type=int, default=settings.API_PORT, help="Port hoat dong")
    server_parser.add_argument("--reload", action="store_true", help="Bat auto-reload khi thay doi file (chi cho dev)")
    server_parser.set_defaults(func=handle_server)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

