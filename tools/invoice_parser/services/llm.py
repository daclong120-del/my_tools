import time
from invoice_parser.models import InvoiceData, InvoiceItem

class LLMService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze_invoice_text(self, text: str) -> InvoiceData:
        # Mo phong do tre khi goi API LLM
        time.sleep(0.8)
        
        # Gia lap viec LLM phan tich text tu file PDF/Image va tra ve JSON dung schema
        # O day chung ta tra ve du lieu tinh dua tren gia thuyet phan tich thanh cong
        return InvoiceData(
            invoice_number="INV-2026-9999",
            date="2026-05-31",
            vendor="Cong ty Cong nghe GptTaste",
            items=[
                InvoiceItem(description="Ban quyen phan mem Chat Widget", quantity=2, price=250.0, amount=500.0),
                InvoiceItem(description="Dich vu setup may chu Cloud", quantity=1, price=1000.0, amount=1000.0)
            ],
            subtotal=1500.0,
            vat=150.0,
            total=1650.0
        )
