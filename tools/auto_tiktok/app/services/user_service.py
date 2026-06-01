from app.schemas.user_schema import UserCreate
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
