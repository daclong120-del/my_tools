from invoice_parser.models import InvoiceData
from typing import List, Tuple

class InvoiceAgent:
    def __init__(self):
        pass

    def run_agent_audit(self, data: InvoiceData) -> Tuple[bool, List[str]]:
        """
        Agent phan tich & kiem tra xem hoa don co bat thuong hay sai lech gi khong.
        Tra ve: (hop_le, danh_sach_canh_bao)
        """
        warnings = []
        
        # 1. Kiem tra tinh toan toan ve: quantity * price == amount
        for idx, item in enumerate(data.items):
            expected_amount = round(item.quantity * item.price, 2)
            if round(item.amount, 2) != expected_amount:
                warnings.append(f"Dong #{idx+1} ('{item.description}'): Thanh tien ({item.amount}) khong khop voi So luong * Don gia ({expected_amount})")
        
        # 2. Kiem tra tinh toan sum(amount) == subtotal
        calculated_subtotal = sum(item.amount for item in data.items)
        if round(data.subtotal, 2) != round(calculated_subtotal, 2):
            warnings.append(f"Tong truoc thue ({data.subtotal}) khong khop voi tong tien cac dong le ({calculated_subtotal})")
            
        # 3. Kiem tra subtotal + vat == total
        expected_total = round(data.subtotal + data.vat, 2)
        if round(data.total, 2) != expected_total:
            warnings.append(f"Tong cong thanh toan ({data.total}) khong khop voi Tong truoc thue + VAT ({expected_total})")
            
        # 4. Kiem tra ten vendor co bi de trong
        if not data.vendor.strip():
            warnings.append("Khong tim thay ten nha cung cap (Vendor)")

        is_valid = len(warnings) == 0
        return is_valid, warnings
