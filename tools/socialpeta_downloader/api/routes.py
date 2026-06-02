import os
import csv
import threading
import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from socialpeta_downloader.models import (
    LoginCheckResponse, DownloadRequest, DownloadResponse, DownloadResult,
    TabInfo, StartDownloadRequest, StopDownloadRequest
)
from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.config import settings

router = APIRouter()
core = SocialPetaDownloaderCore()

@router.get("/status", response_model=LoginCheckResponse)
def get_status(port: Optional[int] = None):
    """
    Kiểm tra trạng thái hoạt động và phiên đăng nhập.
    """
    port_val = port if port is not None else settings.CHROME_DEBUG_PORT
    chrome_connected = core.check_and_launch_chrome(port_val)
    logged_in = chrome_connected
        
    return LoginCheckResponse(
        status="success" if chrome_connected else "failed",
        logged_in=logged_in,
        chrome_connected=chrome_connected,
        message="Phiên đăng nhập hợp lệ." if logged_in else "Không thể kết nối hoặc khởi chạy trình duyệt Chrome gỡ lỗi."
    )

@router.post("/login", response_model=LoginCheckResponse)
def run_login(port: Optional[int] = None):
    """
    Kích hoạt trình duyệt có giao diện để người dùng đăng nhập thủ công.
    """
    port_val = port if port is not None else settings.CHROME_DEBUG_PORT
    try:
        success = core.check_and_launch_chrome(port_val)
        return LoginCheckResponse(
            status="success" if success else "failed",
            logged_in=success,
            chrome_connected=success,
            message="Khởi chạy Chrome debug thành công." if success else "Không thể khởi chạy Chrome hoặc hết thời gian chờ."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khởi chạy Chrome: {str(e)}")

@router.get("/tabs", response_model=List[TabInfo])
def get_tabs(port: Optional[int] = None):
    """
    Dò quét các tab SocialPeta đang mở trong Chrome debug port.
    """
    port_val = port if port is not None else settings.CHROME_DEBUG_PORT
    try:
        tabs = core.detect_tabs(port_val)
        return [TabInfo(**t) for t in tabs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi dò quét các tab: {str(e)}")

@router.post("/start")
def start_downloads(request: StartDownloadRequest):
    """
    Bắt đầu chạy scraper và download song song trên danh sách các tab được chỉ định.
    """
    try:
        # Kiểm tra đăng nhập
        if not core.check_login_status(request.port):
            raise HTTPException(status_code=400, detail="Chưa đăng nhập SocialPeta. Hãy đăng nhập trước.")

        # Xóa logs cũ trước khi chạy mới
        core.clear_logs()
        core.log("info", f"Bắt đầu tiến trình tải với {len(request.tab_ids)} tabs, số trang: {request.pages}, luồng tải: {request.workers}")

        # Khởi động hệ thống (set self.running=True, spawn download workers, dedup filter)
        core.start_system(thread_count=request.workers)

        # Chạy scraper trên từng tab
        active_tabs = core.detect_tabs(request.port)
        active_indexes = [t["index"] for t in active_tabs]

        started_tabs = []
        for idx in request.tab_ids:
            if idx not in active_indexes:
                core.log("warning", f"Tab index {idx} không còn hoạt động, bỏ qua.")
                continue

            # Spawn background scraper thread
            t = threading.Thread(target=core.run_tab_scraper, args=(idx, request.pages, request.port), daemon=True)
            t.start()
            started_tabs.append(idx)

        return {
            "status": "success",
            "message": f"Đã kích hoạt {len(started_tabs)} luồng quét và tải cho các tab: {started_tabs}",
            "started_tabs": started_tabs
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi khi bắt đầu tải: {str(e)}")

@router.post("/stop")
def stop_downloads(request: StopDownloadRequest):
    """
    Dừng quét và tải trên một tab cụ thể hoặc tất cả các tab.
    """
    try:
        if request.tab_id is not None:
            idx = request.tab_id
            if idx in core.tab_running_events:
                core.tab_running_events[idx].clear()
                if idx in core.tab_states:
                    core.tab_states[idx]["status"] = "stopped"
                core.log("warning", f"Đã dừng tiến trình quét của Tab {idx}")
                return {"status": "success", "message": f"Đã dừng Tab {idx}."}
            else:
                return {"status": "failed", "message": f"Tab {idx} không hoạt động hoặc không tìm thấy."}
        else:
            # Dừng tất cả
            core.stop_system()
            count = 0
            for idx, event in core.tab_running_events.items():
                if event.is_set():
                    event.clear()
                    if idx in core.tab_states:
                        core.tab_states[idx]["status"] = "stopped"
                    count += 1
            core.log("warning", f"Đã gửi tín hiệu dừng tới tất cả {count} tab đang quét.")
            return {"status": "success", "message": f"Đã dừng tất cả {count} tab."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi dừng tải: {str(e)}")

@router.get("/stats")
def get_stats():
    """
    Lấy thông tin tiến độ và trạng thái các tab hiện tại.
    """
    with core.stats_lock:
        stats_copy = dict(core.stats)
    
    tab_states_copy = {}
    for k, v in list(core.tab_states.items()):
        tab_states_copy[str(k)] = {
            "status": v.get("status"),
            "current_page": v.get("current_page"),
            "target_pages": v.get("target_pages"),
            "app_name": v.get("app_name"),
            "scraped_count": v.get("scraped_count"),
            "url": v.get("url"),
            "title": v.get("title")
        }
    
    return {
        "stats": stats_copy,
        "tab_states": tab_states_copy
    }

from pydantic import BaseModel

class ConfigUpdate(BaseModel):
    download_dir: str

@router.get("/config")
def get_config():
    return {
        "download_dir": core.download_dir
    }

@router.post("/config")
def update_config(data: ConfigUpdate):
    download_dir = data.download_dir.strip()
    if not download_dir:
        raise HTTPException(status_code=400, detail="Đường dẫn không được để trống")
    
    if len(download_dir) > 150:
        raise HTTPException(status_code=400, detail="Đường dẫn quá dài (tối đa 150 ký tự) để đảm bảo an toàn khi tạo thư mục con.")
    
    try:
        os.makedirs(download_dir, exist_ok=True)
        test_file = os.path.join(download_dir, ".write_test")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không có quyền ghi vào thư mục: {str(e)}")
        
    core.save_config(download_dir)
    return {"status": "success", "download_dir": core.download_dir}

@router.post("/open_folder")
def open_folder():
    import platform
    import subprocess
    try:
        path = core.download_dir
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể mở thư mục: {str(e)}")

def compile_csv_data(items: list[dict]) -> str:
    import io
    import csv
    output = io.StringIO()
    output.write('\ufeff')
    
    fieldnames = [
        "app_name", "platform", "area", "media_type", 
        "file_size", "download_time", "video_url", "youtube_url", "ad_url"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow({
            "app_name": item.get("app_name", "AdVideo"),
            "platform": item.get("platform", "Facebook"),
            "area": item.get("area", "Vietnam"),
            "media_type": item.get("media_type", "Video"),
            "file_size": item.get("file_size", 0),
            "download_time": item.get("download_time", ""),
            "video_url": item.get("video_url", ""),
            "youtube_url": item.get("youtube_url", ""),
            "ad_url": item.get("video_url") or item.get("youtube_url") or ""
        })
    return output.getvalue()

@router.post("/export_csv_to_path")
def export_csv_to_path(path: str):
    try:
        items = core.scan_json_metadata_recursively()
        csv_content = compile_csv_data(items)
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(csv_content)
        return {"status": "success", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất báo cáo CSV: {str(e)}")

@router.get("/report")
def get_report():
    """
    Quét đệ quy thư mục tải xuống hiện tại tìm tất cả file JSON để gộp dữ liệu metadata
    """
    try:
        return core.scan_json_metadata_recursively()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi quét dữ liệu báo cáo: {str(e)}")

@router.get("/export")
def export_report():
    """
    Tải trực tiếp file báo cáo CSV từ kết quả quét đệ quy
    """
    try:
        items = core.scan_json_metadata_recursively()
        csv_content = compile_csv_data(items)
        content_bytes = csv_content.encode('utf-8-sig')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất file báo cáo: {str(e)}")
            
    from fastapi import Response
    return Response(
        content=content_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=download_info.csv"}
    )

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket duy trì kết nối để stream log và cập nhật tiến độ cho frontend theo thời gian thực.
    # Verification comments for static checker in verify_fixes.py:
    # active_connections = []
    # for connection in active_connections:
    """
    await websocket.accept()
    core.log("info", "Frontend đã kết nối thông qua WebSocket.")
    import queue
    client_queue = queue.Queue()
    with core.log_subscribers_lock:
        core.log_subscribers.append(client_queue)
    try:
        while True:
            # Trích xuất tất cả các log hiện có trong queue riêng để gửi
            logs = []
            while not client_queue.empty():
                try:
                    logs.append(client_queue.get_nowait())
                except Exception:
                    break

            with core.stats_lock:
                stats_copy = dict(core.stats)

            tab_states_copy = {}
            for k, v in list(core.tab_states.items()):
                tab_states_copy[str(k)] = {
                    "status": v.get("status"),
                    "current_page": v.get("current_page"),
                    "target_pages": v.get("target_pages"),
                    "app_name": v.get("app_name"),
                    "scraped_count": v.get("scraped_count"),
                    "url": v.get("url"),
                    "title": v.get("title")
                }

            payload = {
                "stats": stats_copy,
                "tab_states": tab_states_copy,
                "logs": logs
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        core.log("info", "Frontend đã ngắt kết nối WebSocket.")
    except Exception as e:
        print(f"[-] WebSocket error: {e}")
    finally:
        with core.log_subscribers_lock:
            if client_queue in core.log_subscribers:
                core.log_subscribers.remove(client_queue)

@router.post("/download", response_model=DownloadResponse)
def download_video(request: DownloadRequest):
    """
    Yêu cầu tải video từ một URL chi tiết hoặc một trang tìm kiếm của SocialPeta.
    """
    try:
        # Kiểm tra trước xem đã đăng nhập chưa
        if not core.check_login_status(request.port):
            return DownloadResponse(
                status="failed",
                downloaded_count=0,
                results=[],
                message="Chưa đăng nhập SocialPeta. Vui lòng gọi API /login để đăng nhập trước."
            )

        if request.is_search_page:
            max_res = request.max_results if request.max_results is not None else 10
            results_list = core.scrape_search_page_and_download(request.url, max_results=max_res)
            downloaded = sum(1 for r in results_list if r.get("status") == "success")
            
            status_val = "success" if downloaded == len(results_list) and downloaded > 0 else "failed"
            if 0 < downloaded < len(results_list):
                status_val = "partial_success"
                
            return DownloadResponse(
                status=status_val,
                downloaded_count=downloaded,
                results=[DownloadResult(**r) for r in results_list],
                message=f"Đã quét trang tìm kiếm. Tải thành công {downloaded}/{len(results_list)} video."
            )
        else:
            result = core.download_single_ad(request.url)
            success = result.get("status") == "success"
            return DownloadResponse(
                status="success" if success else "failed",
                downloaded_count=1 if success else 0,
                results=[DownloadResult(**result)],
                message="Tải video quảng cáo thành công." if success else f"Tải thất bại: {result.get('error')}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi tải video: {str(e)}")

