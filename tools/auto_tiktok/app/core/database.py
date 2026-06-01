# Thiết lập kết nối Async Database (Khung thô tham khảo)
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
