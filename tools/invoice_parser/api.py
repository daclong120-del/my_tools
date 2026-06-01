from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from invoice_parser.config import settings
from invoice_parser.routes import router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for parsing invoices with Agent verification",
    version="1.1.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1/invoice")

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": "/docs",
        "status_url": "/api/v1/invoice/status"
    }

if __name__ == "__main__":
    import uvicorn
    # Chay tu thu muc backends/ de import dung package invoice_parser
    uvicorn.run("invoice_parser.api:app", host=settings.HOST, port=settings.API_PORT, reload=True)
