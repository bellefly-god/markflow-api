"""
MarkFlow API - Document to Markdown Conversion Service
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
import sys

from app.core.config import settings
from app.api.routes import router as api_router


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO" if not settings.DEBUG else "DEBUG"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"API Prefix: {settings.API_PREFIX}")
    logger.info(f"Max file size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB")
    logger.info(f"LLM enabled: {settings.OPENAI_API_KEY is not None}")
    
    # Startup
    yield
    
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## MarkFlow API

Convert documents to clean Markdown for LLMs and AI applications.

### Supported Formats
- **PDF** - Portable Document Format
- **DOCX** - Microsoft Word
- **PPTX** - Microsoft PowerPoint
- **XLSX/XLS** - Microsoft Excel
- **HTML** - Web pages
- **Images** - PNG, JPG, GIF (with OCR)
- **Audio** - MP3, WAV (with transcription)
- **Data** - CSV, JSON, XML
- **Other** - EPUB, ZIP

### OpenAI-Compatible Endpoints
Use with any OpenAI SDK or tool:
- `POST /v1/chat/completions` - Chat completions
- `GET /v1/models` - List models

### Authentication
Provide your API key in the `X-API-Key` header or `Authorization: Bearer <key>` header.
    """,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    lifespan=lifespan
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "detail": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# Include routers
app.include_router(api_router, prefix=settings.API_PREFIX)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_PREFIX}/docs",
        "health": f"{settings.API_PREFIX}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
