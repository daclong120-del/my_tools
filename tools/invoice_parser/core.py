from invoice_parser.config import settings
from invoice_parser.services.storage import StorageService
from invoice_parser.services.llm import LLMService
from invoice_parser.services.external import ExternalService
from invoice_parser.models import ParseResponse, InvoiceData

class InvoiceParserCore:
    def __init__(self):
        self.storage = StorageService(settings.UPLOAD_DIR)
        self.llm = LLMService(settings.LLM_API_KEY)
        self.external = ExternalService()

    def process_invoice_file(self, filename: str, content_type: str, file_content: bytes, sync_external: bool = False) -> ParseResponse:
        # 1. Luu file
        file_path = self.storage.save_file(filename, file_content)
        
        # 2. Doc text (gia lap doc tu file_path)
        mock_extracted_text = f"Noidung text tu file hoa don {filename}..."
        
        # 3. Goi LLM de phan tich
        invoice_data = self.llm.analyze_invoice_text(mock_extracted_text)
        
        # 4. Dong bo ben ngoai neu duoc yeu cau
        sync_result = None
        if sync_external:
            sync_result = self.external.sync_to_accounting_system(invoice_data)
            
        return ParseResponse(
            status="success",
            file_name=filename,
            content_type=content_type,
            extracted_data=invoice_data
        )

    def process_invoice_from_path(self, file_path: str, sync_external: bool = False) -> InvoiceData:
        # Phuong thuc nay thuong dung cho CLI (truyen duong dan tuc thi)
        import os
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Khong tim thay file tai: {file_path}")
            
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            content = f.read()
            
        response = self.process_invoice_file(filename, "application/octet-stream", content, sync_external)
        return response.extracted_data
