import uvicorn
from fastapi import FastAPI
from app.api.routes.user_router import router as user_router
from app.api.routes.product_router import router as product_router

app = FastAPI(
    title="Auto TikTok API",
    description="Khung thô API của công cụ Auto TikTok sử dụng kiến trúc phân tầng chuẩn",
    version="1.0.0"
)

# Đăng ký router từ tầng HTTP
app.include_router(user_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Auto TikTok API Boilerplate"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
