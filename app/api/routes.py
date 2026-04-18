"""
Main API routes for MarkFlow
"""
import os
import io
import uuid
import time
from typing import Optional, List
from datetime import datetime
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File,
    Form, Header, Request, BackgroundTasks
)
from fastapi.responses import StreamingResponse, JSONResponse, Response
import aiofiles

from app.models.schemas import (
    ConversionResponse, AISummaryResponse, ConvertAndSummarizeResponse,
    ErrorResponse, HealthResponse, UsageStats,
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatCompletionUsage, ChatMessage, ModelsResponse, ModelInfo,
    BatchJobResponse, BatchJobStatus, BatchDownloadResponse
)
from app.services.converter import document_service
from app.services.batch import batch_service, TaskStatus
from app.core.config import settings
from app.core.security import verify_api_key, hash_api_key
from loguru import logger


router = APIRouter()

# In-memory API keys store (in production, use database)
API_KEYS_DB = {
    # Demo key: mf_demo_key_for_testing
    hash_api_key("mf_demo_key_for_testing"): {
        "name": "Demo Key",
        "owner": "demo",
        "rate_limit": 1000,
        "is_active": True
    }
}

# Usage tracking
USAGE_STATS = {
    "total_conversions": 0,
    "total_tokens": 0,
    "total_files": 0,
    "by_format": {},
    "start_time": time.time()
}


async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """Extract API key from headers"""
    if x_api_key:
        return x_api_key
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def verify_auth(api_key: Optional[str] = Depends(get_api_key)) -> dict:
    """Verify API key authentication"""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header or Authorization: Bearer <key>"
        )
    
    key_hash = hash_api_key(api_key)
    if key_hash not in API_KEYS_DB:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    key_info = API_KEYS_DB[key_hash]
    if not key_info.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail="API key is disabled"
        )
    
    return key_info


# ==================== Health & Info ====================

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        uptime_seconds=time.time() - USAGE_STATS["start_time"],
        services={
            "converter": True,
            "llm": document_service.llm_client is not None,
            "redis": False  # TODO: check Redis connection
        }
    )


@router.get("/models", response_model=ModelsResponse, tags=["OpenAI Compatible"])
async def list_models():
    """List available models (OpenAI-compatible)"""
    models = [
        ModelInfo(
            id="markflow-convert",
            object="model",
            created=int(time.time()),
            owned_by="markflow",
            permission=[],
            root="markflow-convert",
            parent=None
        ),
        ModelInfo(
            id="markflow-summarize",
            object="model",
            created=int(time.time()),
            owned_by="markflow",
            permission=[],
            root="markflow-summarize",
            parent=None
        ),
        ModelInfo(
            id="markflow-full",
            object="model",
            created=int(time.time()),
            owned_by="markflow",
            permission=[],
            root="markflow-full",
            parent=None
        )
    ]
    return ModelsResponse(object="list", data=models)


@router.get("/usage", response_model=UsageStats, tags=["System"])
async def get_usage(key_info: dict = Depends(verify_auth)):
    """Get usage statistics"""
    return UsageStats(**USAGE_STATS)


# ==================== Document Conversion ====================

@router.post(
    "/convert",
    response_model=ConversionResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    tags=["Conversion"]
)
async def convert_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to convert"),
    use_ai_description: bool = Form(False, description="Use AI for image descriptions"),
    key_info: dict = Depends(verify_auth)
):
    """
    Convert a document to Markdown.
    
    Supported formats: PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML, Images, Audio
    """
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}. Supported: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    try:
        # Perform conversion
        result = await document_service.convert(
            file_content=content,
            file_name=file.filename,
            use_ai_description=use_ai_description
        )
        
        # Update stats
        USAGE_STATS["total_conversions"] += 1
        USAGE_STATS["total_files"] += 1
        file_type = result.file_type
        USAGE_STATS["by_format"][file_type] = USAGE_STATS["by_format"].get(file_type, 0) + 1
        
        return ConversionResponse(
            success=True,
            text_content=result.text_content,
            file_name=result.file_name,
            file_type=result.file_type,
            file_size=result.file_size,
            duration_ms=int(result.duration * 1000),
            markdown_length=result.markdown_length,
            metadata=result.metadata
        )
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post(
    "/summarize",
    response_model=AISummaryResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    tags=["Conversion"]
)
async def summarize_document(
    content: str = Form(..., description="Markdown content to summarize"),
    file_name: Optional[str] = Form(None, description="Original file name"),
    key_info: dict = Depends(verify_auth)
):
    """
    Generate AI summary of markdown content.
    
    Returns summary, key points, document type, and tags.
    """
    try:
        result = await document_service.summarize(
            markdown_content=content,
            file_name=file_name or "document.md"
        )
        
        USAGE_STATS["total_tokens"] += result.tokens_used
        
        return AISummaryResponse(
            success=True,
            summary=result.summary,
            key_points=result.key_points,
            document_type=result.document_type,
            tags=result.tags,
            reading_time=result.reading_time,
            tokens_used=result.tokens_used
        )
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


@router.post(
    "/convert-and-summarize",
    response_model=ConvertAndSummarizeResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    tags=["Conversion"]
)
async def convert_and_summarize(
    file: UploadFile = File(..., description="File to convert"),
    use_ai_description: bool = Form(False),
    key_info: dict = Depends(verify_auth)
):
    """
    Convert document to Markdown and generate AI summary in one request.
    """
    # Validate file
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}"
        )
    
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum: {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    try:
        # Convert
        conversion_result = await document_service.convert(
            file_content=content,
            file_name=file.filename,
            use_ai_description=use_ai_description
        )
        
        # Summarize
        summary_result = await document_service.summarize(
            markdown_content=conversion_result.text_content,
            file_name=file.filename
        )
        
        # Update stats
        USAGE_STATS["total_conversions"] += 1
        USAGE_STATS["total_files"] += 1
        USAGE_STATS["total_tokens"] += summary_result.tokens_used
        
        return ConvertAndSummarizeResponse(
            success=True,
            conversion=ConversionResponse(
                success=True,
                text_content=conversion_result.text_content,
                file_name=conversion_result.file_name,
                file_type=conversion_result.file_type,
                file_size=conversion_result.file_size,
                duration_ms=int(conversion_result.duration * 1000),
                markdown_length=conversion_result.markdown_length,
                metadata=conversion_result.metadata
            ),
            summary=AISummaryResponse(
                success=True,
                summary=summary_result.summary,
                key_points=summary_result.key_points,
                document_type=summary_result.document_type,
                tags=summary_result.tags,
                reading_time=summary_result.reading_time,
                tokens_used=summary_result.tokens_used
            )
        )
    except Exception as e:
        logger.error(f"Convert and summarize failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OpenAI-Compatible Chat Completions ====================

@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    tags=["OpenAI Compatible"]
)
async def chat_completions(
    request: ChatCompletionRequest,
    key_info: dict = Depends(verify_auth)
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Special behaviors:
    - If file_url is provided, convert the file first
    - Model 'markflow-convert' returns converted markdown
    - Model 'markflow-summarize' returns AI summary
    - Model 'markflow-full' returns both
    """
    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    
    # Get the last user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break
    
    # Determine response based on model
    model = request.model
    
    try:
        if model == "markflow-convert":
            # For convert model, expect file content in message
            response_content = user_message  # Echo back or process
            
        elif model == "markflow-summarize":
            # Summarize the provided content
            result = await document_service.summarize(
                markdown_content=user_message,
                file_name="input.md"
            )
            response_content = f"""## Summary
{result.summary}

## Key Points
{chr(10).join(f'- {p}' for p in result.key_points)}

## Document Type
{result.document_type}

## Tags
{', '.join(result.tags)}

## Reading Time
~{result.reading_time} minutes"""
            
        elif model == "markflow-full":
            result = await document_service.summarize(
                markdown_content=user_message,
                file_name="input.md"
            )
            response_content = f"""# Converted Document

{user_message[:2000]}...

---

## AI Analysis

**Summary:** {result.summary}

**Key Points:**
{chr(10).join(f'- {p}' for p in result.key_points)}

**Type:** {result.document_type} | **Tags:** {', '.join(result.tags)} | **Reading Time:** ~{result.reading_time} min"""
        else:
            response_content = f"Unknown model: {model}. Available models: markflow-convert, markflow-summarize, markflow-full"
        
        # Calculate tokens (approximate)
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_tokens = len(response_content.split())
        
        return ChatCompletionResponse(
            id=request_id,
            object="chat.completion",
            created=created,
            model=model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=response_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== API Key Management ====================

@router.post("/keys/generate", tags=["API Keys"])
async def generate_api_key(
    name: str = Form(...),
    owner: str = Form(...),
    rate_limit: int = Form(100),
    key_info: dict = Depends(verify_auth)
):
    """Generate a new API key (requires admin key)"""
    from app.core.security import generate_api_key, hash_api_key
    
    new_key = generate_api_key()
    key_hash = hash_api_key(new_key)
    
    API_KEYS_DB[key_hash] = {
        "name": name,
        "owner": owner,
        "rate_limit": rate_limit,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {
        "success": True,
        "api_key": new_key,  # Only shown once!
        "name": name,
        "owner": owner,
        "rate_limit": rate_limit
    }


@router.get("/keys/list", tags=["API Keys"])
async def list_api_keys(key_info: dict = Depends(verify_auth)):
    """List all API keys (hashed)"""
    return {
        "keys": [
            {
                "name": info["name"],
                "owner": info["owner"],
                "is_active": info.get("is_active", True),
                "rate_limit": info.get("rate_limit", 100)
            }
            for info in API_KEYS_DB.values()
        ]
    }


# ==================== Batch Conversion ====================

@router.post(
    "/batch-convert",
    response_model=BatchJobResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    tags=["Batch"]
)
async def create_batch_job(
    files: List[UploadFile] = File(..., description="Files to convert"),
    key_info: dict = Depends(verify_auth)
):
    """
    Create a batch conversion job.
    
    Upload multiple files for conversion. Returns a job_id for tracking.
    Use /batch-status/{job_id} to check progress.
    Use /batch-download/{job_id} to download results as ZIP.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")
    
    # Read all files
    file_data = []
    for file in files:
        # Validate extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {file.filename} ({file_ext})"
            )
        
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {file.filename}"
            )
        
        file_data.append((file.filename, content))
    
    # Create batch job
    job_id = await batch_service.create_job(file_data)
    
    # Update stats
    USAGE_STATS["total_files"] += len(files)
    
    return BatchJobResponse(
        success=True,
        job_id=job_id,
        total_files=len(files),
        message=f"Batch job created with {len(files)} files"
    )


@router.get(
    "/batch-status/{job_id}",
    response_model=BatchJobStatus,
    responses={404: {"model": ErrorResponse}},
    tags=["Batch"]
)
async def get_batch_status(
    job_id: str,
    key_info: dict = Depends(verify_auth)
):
    """
    Get batch job status.
    
    Returns progress, completed files, and task details.
    """
    status = batch_service.get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return BatchJobStatus(**status)


@router.get(
    "/batch-download/{job_id}",
    responses={404: {"model": ErrorResponse}},
    tags=["Batch"]
)
async def download_batch_result(
    job_id: str,
    key_info: dict = Depends(verify_auth)
):
    """
    Download batch conversion results as ZIP.
    
    Returns a ZIP file containing all converted .md files.
    Only available when job status is 'completed'.
    """
    status = batch_service.get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    if status["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {status['status']}"
        )
    
    zip_content = batch_service.generate_zip(job_id)
    if not zip_content:
        raise HTTPException(status_code=500, detail="Failed to generate ZIP")
    
    # Return ZIP file
    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=markflow-{job_id}.zip"
        }
    )


@router.delete("/batch/{job_id}", tags=["Batch"])
async def delete_batch_job(
    job_id: str,
    key_info: dict = Depends(verify_auth)
):
    """Delete a batch job and free memory"""
    batch_service.cleanup_job(job_id)
    return {"success": True, "message": f"Job {job_id} deleted"}
