from fastapi import APIRouter

router = APIRouter(tags=["products"])

@router.get("/products")
async def get_products():
    # Khung thô router sản phẩm
    return {"message": "List of products"}
