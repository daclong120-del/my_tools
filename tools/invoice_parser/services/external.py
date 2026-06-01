import time
from invoice_parser.models import InvoiceData

class ExternalService:
    @staticmethod
    def sync_to_accounting_system(data: InvoiceData) -> dict:
        # Gia lap dong bo hoa du lieu sang he thong ke toan ben thu 3 (vi du QuickBooks, SAP...)
        time.sleep(0.3)
        return {
            "synced": True,
            "external_id": f"ACC-EXT-{data.invoice_number}",
            "vendor_name": data.vendor,
            "total_amount": data.total
        }
