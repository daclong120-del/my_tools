from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):   # Dữ liệu CLIENT GỬI VÀO
    name: str
    email: EmailStr
    password: str

class UserResponse(BaseModel): # Dữ liệu SERVER TRẢ RA
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True
