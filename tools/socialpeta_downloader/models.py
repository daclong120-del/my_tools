from pydantic import BaseModel, Field
from typing import List, Optional

class LoginCheckResponse(BaseModel):
    status: str = Field("success", description="Trang thai kiem tra")
    logged_in: bool = Field(..., description="Trang thai dang nhap thuc te cua phien Chrome")
    chrome_connected: bool = Field(False, description="Chrome debug port co dang mo hay khong")
    message: Optional[str] = Field(None, description="Thong tin chi tiet")

class DownloadRequest(BaseModel):
    url: str = Field(..., description="Link chi tiet quang cao hoac link tim kiem cua SocialPeta")
    is_search_page: bool = Field(False, description="Xac dinh day co phai la link tim kiem khong (de tu dong cuon va cao nhieu ad)")
    max_results: Optional[int] = Field(10, description="So luong video toi da muon tai neu la trang tim kiem")
    port: Optional[int] = Field(None, description="Chrome remote debugging port")

class DownloadResult(BaseModel):
    ad_id: str = Field(..., description="ID quang cao tren SocialPeta")
    ad_url: str = Field(..., description="Link den trang chi tiet")
    video_url: Optional[str] = Field(None, description="Link CDN video lay duoc")
    title: Optional[str] = Field(None, description="Tieu de hoac mo ta ngan cua quang cao")
    saved_path: Optional[str] = Field(None, description="Duong dan luu file video (.mp4) trong o dia")
    status: str = Field("success", description="Ket qua tai: success hoac failed")
    error: Optional[str] = Field(None, description="Chi tiet loi neu tai that bai")

class DownloadResponse(BaseModel):
    status: str = Field("success", description="Trang thai tong quat cua request")
    downloaded_count: int = Field(0, description="So luong video da tai thanh cong")
    results: List[DownloadResult] = Field(default=[], description="Ket qua chi tiet cua tung quang cao")
    message: Optional[str] = Field(None, description="Thong bao loi hoac thong tin them")

class TabInfo(BaseModel):
    index: int = Field(..., description="Stable 1-based index of the tab")
    tab_id: str = Field(..., description="Stable window.__tab_id value")
    url: str = Field(..., description="Current URL of the tab")
    title: str = Field(..., description="Page title of the tab")

class StartDownloadRequest(BaseModel):
    tab_ids: List[int] = Field(..., description="List of tab indexes to scrape and download")
    pages: int = Field(5, description="Number of pages to paginate")
    workers: int = Field(5, description="Number of parallel download threads/workers")
    port: Optional[int] = Field(None, description="Chrome remote debugging port")

class StopDownloadRequest(BaseModel):
    tab_id: Optional[int] = Field(None, description="Tab index to stop. If not specified, stops all active tab scraping.")

