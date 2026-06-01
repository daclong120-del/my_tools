import os

# Define the directory structure and file contents
structure = {
    "app": {
        "__init__.py": "",
        "api": {
            "__init__.py": "",
            "routes": {
                "__init__.py": "from .user_router import router as user_router\n",
                "user_router.py": '''from fastapi import APIRouter, HTTPException, status
from app.schemas.user_schema import UserCreate, UserResponse
from app.services.user_service import UserService

router = APIRouter(tags=["users"])

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate):
    # KHÔNG xử lý logic ở đây
    # Chỉ nhận request → gọi service → trả response
    try:
        return await UserService.create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
''',
                "product_router.py": '''from fastapi import APIRouter

router = APIRouter(tags=["products"])

@router.get("/products")
async def get_products():
    # Khung thô router sản phẩm
    return {"message": "List of products"}
'''
            }
        },
        "schemas": {
            "__init__.py": "",
            "user_schema.py": '''from pydantic import BaseModel, EmailStr

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
'''
        },
        "services": {
            "__init__.py": "",
            "user_service.py": '''from app.schemas.user_schema import UserCreate
from app.repositories.user_repo import UserRepo

class UserService:
    @staticmethod
    async def create_user(data: UserCreate):
        # Xử lý logic: hash password, kiểm tra email trùng...
        existing_user = await UserRepo.get_by_email(data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Giả lập hash mật khẩu thô
        hashed_pw = f"hashed_{data.password}"
        
        # Gọi repository để thực hiện lưu trữ DB
        return await UserRepo.insert(data.name, data.email, hashed_pw)
'''
        },
        "repositories": {
            "__init__.py": "",
            "user_repo.py": '''# Giả lập Database trong bộ nhớ cho khung thô chạy thử nghiệm
class UserMockDB:
    users = []
    counter = 0

class UserRepo:
    @staticmethod
    async def get_by_email(email: str):
        # Chỉ query DB tìm kiếm user
        for user in UserMockDB.users:
            if user["email"] == email:
                return user
        return None

    @staticmethod
    async def insert(name: str, email: str, hashed_pw: str):
        # Chỉ lo thao tác ghi/đọc DB, không có logic nghiệp vụ
        UserMockDB.counter += 1
        new_user = {
            "id": UserMockDB.counter,
            "name": name,
            "email": email,
            "password": hashed_pw
        }
        UserMockDB.users.append(new_user)
        return new_user
'''
        },
        "models": {
            "__init__.py": "",
            "user_model.py": '''# Định nghĩa SQLAlchemy Model / SQLModel (Khung thô tham khảo)
"""
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
"""
'''
        },
        "core": {
            "__init__.py": "",
            "config.py": '''import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Auto TikTok API"
    API_V1_STR: str = "/api/v1"
    
    # Cấu hình Database thô
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

    class Config:
        case_sensitive = True

settings = Settings()
''',
            "database.py": '''# Thiết lập kết nối Async Database (Khung thô tham khảo)
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

# Dependency cung cấp DB Session cho router khi cần
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
          finally:
            await session.close()
"""
'''
        }
    },
    "main.py": '''import uvicorn
from fastapi import FastAPI
from app.api.routes import user_router

app = FastAPI(title="Auto TikTok API", version="1.0.0")

# Đăng ký router từ tầng HTTP
app.include_router(user_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Auto TikTok API Boilerplate"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
'''
}

def create_files_and_dirs(base_path, struct):
    for name, content in struct.items():
        path = os.path.join(base_path, name)
        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            create_files_and_dirs(path, content)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Created file: {path}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Initializing boilerplate in: {current_dir}")
    create_files_and_dirs(current_dir, structure)
    print("FastAPI boilerplate initialization complete!")
