from fastapi import APIRouter, HTTPException, Query
from app.services import WebScraperService

router = APIRouter()

@router.get("/status")
def get_status():
    return {"status": "ok", "service": "web_scraper"}

@router.get("/scrape")
def scrape_url(url: str = Query(..., description="URL cua trang web can cao du lieu")):
    try:
        result = WebScraperService.scrape_url(url)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi khi cao URL: {str(e)}")
