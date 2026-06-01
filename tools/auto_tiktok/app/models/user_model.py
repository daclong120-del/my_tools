# Định nghĩa SQLAlchemy Model / SQLModel (Khung thô tham khảo)
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
