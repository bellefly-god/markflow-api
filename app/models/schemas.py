"""
Pydantic models for API requests and responses
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


# ==================== Enums ====================

class FileFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    IMAGE = "image"
    AUDIO = "audio"
    OTHER = "other"


class ConversionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Request Models ====================

class ConvertRequest(BaseModel):
    """Request for document conversion"""
    use_ai_description: bool = Field(
        default=False,
        description="Use AI to describe images in the document"
    )
    include_summary: bool = Field(
        default=False,
        description="Generate AI summary of the document"
    )


class SummarizeRequest(BaseModel):
    """Request for document summarization"""
    content: str = Field(..., description="Markdown content to summarize")
    file_name: Optional[str] = Field(None, description="Original file name")
    max_points: int = Field(default=5, ge=1, le=10, description="Maximum key points")


class BatchConvertRequest(BaseModel):
    """Request for batch conversion"""
    files: List[str] = Field(..., description="List of file URLs or IDs")
    use_ai_description: bool = False


# ==================== Response Models ====================

class ConversionMetadata(BaseModel):
    """Metadata about the conversion"""
    source: str = "markitdown"
    converted_at: str
    duration_ms: int
    markdown_length: int


class ConversionResponse(BaseModel):
    """Response for document conversion"""
    success: bool = True
    text_content: str = Field(..., description="Converted markdown content")
    file_name: str
    file_type: str
    file_size: int
    duration_ms: int
    markdown_length: int
    metadata: Optional[Dict[str, Any]] = None


class AISummaryResponse(BaseModel):
    """Response for AI summarization"""
    success: bool = True
    summary: str
    key_points: List[str]
    document_type: str
    tags: List[str]
    reading_time: int
    tokens_used: int = 0


class ConvertAndSummarizeResponse(BaseModel):
    """Combined response for conversion + summarization"""
    success: bool = True
    conversion: ConversionResponse
    summary: Optional[AISummaryResponse] = None


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str
    uptime_seconds: float
    services: Dict[str, bool]


class APIKeyResponse(BaseModel):
    """API key response"""
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class UsageStats(BaseModel):
    """Usage statistics"""
    total_conversions: int
    total_tokens: int
    total_files: int
    by_format: Dict[str, int]


# ==================== OpenAI-Compatible Models ====================

class ChatMessage(BaseModel):
    """Chat message for OpenAI-compatible API"""
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request"""
    model: str = "markflow-convert"
    messages: List[ChatMessage]
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = None
    stream: bool = False
    user: Optional[str] = None
    
    # MarkFlow extensions
    file_url: Optional[str] = Field(
        None,
        description="URL to a file to convert before chat"
    )
    include_summary: bool = Field(
        default=False,
        description="Include AI summary in response"
    )


class ChatCompletionChoice(BaseModel):
    """Chat completion choice"""
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage information"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ModelInfo(BaseModel):
    """Model information for /models endpoint"""
    id: str
    object: str = "model"
    created: int
    owned_by: str = "markflow"
    permission: List[Dict[str, Any]] = []
    root: str
    parent: Optional[str] = None


class ModelsResponse(BaseModel):
    """Response for /models endpoint"""
    object: str = "list"
    data: List[ModelInfo]


# ==================== Batch Conversion Models ====================

class BatchJobResponse(BaseModel):
    """Response for batch job creation"""
    success: bool = True
    job_id: str
    total_files: int
    message: str = "Batch job created"


class BatchTaskStatus(BaseModel):
    """Status of a single task in batch job"""
    task_id: str
    file_name: str
    status: str
    error: Optional[str] = None


class BatchJobStatus(BaseModel):
    """Response for batch job status"""
    job_id: str
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    progress: float
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    tasks: List[BatchTaskStatus] = []


class BatchDownloadResponse(BaseModel):
    """Response for batch download"""
    success: bool = True
    job_id: str
    download_url: Optional[str] = None
    message: str
