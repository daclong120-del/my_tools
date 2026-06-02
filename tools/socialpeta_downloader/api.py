import sys
import io

class SafeStreamWrapper:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, data):
        if not self.original_stream:
            return
        try:
            self.original_stream.write(data)
        except UnicodeEncodeError:
            try:
                if hasattr(self.original_stream, 'buffer'):
                    self.original_stream.buffer.write(data.encode('utf-8'))
                else:
                    self.original_stream.write(data.encode('ascii', errors='backslashreplace').decode('ascii'))
            except Exception:
                try:
                    self.original_stream.write(data.encode('ascii', errors='ignore').decode('ascii'))
                except Exception:
                    pass

    def flush(self):
        if self.original_stream and hasattr(self.original_stream, 'flush'):
            try:
                self.original_stream.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self.original_stream, name)

if sys.stdout is not None and not isinstance(sys.stdout, SafeStreamWrapper):
    sys.stdout = SafeStreamWrapper(sys.stdout)
if sys.stderr is not None and not isinstance(sys.stderr, SafeStreamWrapper):
    sys.stderr = SafeStreamWrapper(sys.stderr)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from socialpeta_downloader.config import settings
from socialpeta_downloader.api.routes import router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for automating browser to download SocialPeta videos",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def custom_cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and (origin.startswith("file://") or origin == "null"):
        if request.method == "OPTIONS":
            from fastapi.responses import Response
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
        
    return await call_next(request)

app.include_router(router, prefix="/api/v1/socialpeta")

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": "/docs",
        "status_url": "/api/v1/socialpeta/status"
    }

@app.get("/health")
def health_check():
    yt_dlp_status = "missing"
    yt_dlp_version = None
    try:
        import yt_dlp
        yt_dlp_status = "ok"
        yt_dlp_version = getattr(yt_dlp, "version", None)
        if yt_dlp_version:
            yt_dlp_version = getattr(yt_dlp_version, "__version__", str(yt_dlp_version))
    except ImportError:
        pass
    return {
        "status": "ready",
        "yt_dlp": yt_dlp_status,
        "yt_dlp_version": yt_dlp_version
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.API_PORT)
