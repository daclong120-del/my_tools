from pydantic import BaseModel, Field
from typing import List, Optional

class InvoiceItem(BaseModel):
    description: str = Field(..., description="Mo ta mat hang")
    quantity: int = Field(..., description="So luong")
    price: float = Field(..., description="Don gia")
    amount: float = Field(..., description="Thanh tien")

class InvoiceData(BaseModel):
    invoice_number: str = Field(..., description="So hoa don")
    date: str = Field(..., description="Ngay xuat hoa don")
    vendor: str = Field(..., description="Don vi ban hang")
    items: List[InvoiceItem] = Field(default=[], description="Danh sach mat hang")
    subtotal: float = Field(..., description="Tong tien truoc thue")
    vat: float = Field(..., description="Thue VAT")
    total: float = Field(..., description="Tong cong thanh toan")

class ParseResponse(BaseModel):
    status: str = Field("success", description="Trang thai xu ly")
    file_name: str = Field(..., description="Ten file hoa don")
    content_type: str = Field(..., description="Dinh dang file")
    extracted_data: InvoiceData = Field(..., description="Du lieu da duoc trich xuat")
