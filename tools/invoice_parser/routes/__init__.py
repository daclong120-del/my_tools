from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from invoice_parser.core import InvoiceParserCore
from invoice_parser.agent import InvoiceAgent
from invoice_parser.models import ParseResponse, InvoiceData

router = APIRouter()
core = InvoiceParserCore()
agent = InvoiceAgent()

@router.get("/status")
def get_status():
    return {"status": "ok", "service": "invoice_parser_full"}

@router.post("/parse", response_model=ParseResponse)
async def parse_invoice(file: UploadFile = File(...), sync_external: bool = Query(False)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Ten file khong dung quy cach")
    
    try:
        content = await file.read()
        result = core.process_invoice_file(file.filename, file.content_type, content, sync_external)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi xu ly hoa don: {str(e)}")

@router.post("/audit")
def audit_invoice(data: InvoiceData):
    """
    Endpoint goi Agent de phan tich, kiem tra cac loi sai sot tren hoa don
    """
    is_valid, warnings = agent.run_agent_audit(data)
    return {
        "is_valid": is_valid,
        "warnings": warnings,
        "audit_status": "clean" if is_valid else "has_issues"
    }
