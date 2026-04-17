"""
Core document conversion service using MarkItDown
"""
import os
import io
import json
import tempfile
import hashlib
from typing import Optional, Dict, Any, BinaryIO
from pathlib import Path
from datetime import datetime
import aiofiles

from markitdown import MarkItDown
from openai import AsyncOpenAI

from app.core.config import settings
from loguru import logger


class ConversionResult:
    """Result of document conversion"""
    def __init__(
        self,
        text_content: str,
        file_name: str,
        file_type: str,
        file_size: int,
        duration: float,
        markdown_length: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.text_content = text_content
        self.file_name = file_name
        self.file_type = file_type
        self.file_size = file_size
        self.duration = duration
        self.markdown_length = markdown_length
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_content": self.text_content,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "duration_ms": int(self.duration * 1000),
            "markdown_length": self.markdown_length,
            "metadata": self.metadata
        }


class AISummaryResult:
    """Result of AI summarization"""
    def __init__(
        self,
        summary: str,
        key_points: list[str],
        document_type: str,
        tags: list[str],
        reading_time: int,
        tokens_used: int = 0
    ):
        self.summary = summary
        self.key_points = key_points
        self.document_type = document_type
        self.tags = tags
        self.reading_time = reading_time
        self.tokens_used = tokens_used
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "key_points": self.key_points,
            "document_type": self.document_type,
            "tags": self.tags,
            "reading_time": reading_time,
            "tokens_used": self.tokens_used
        }


class DocumentService:
    """Document conversion service using MarkItDown"""
    
    def __init__(self):
        # Initialize MarkItDown with optional Azure Document Intelligence
        self.markitdown = MarkItDown(
            docintel_endpoint=settings.AZURE_DOC_INTEL_ENDPOINT,
            enable_plugins=True
        )
        
        # Initialize OpenAI client
        self.llm_client = None
        if settings.OPENAI_API_KEY:
            self.llm_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
            )
            self.llm_model = settings.LLM_MODEL
    
    async def convert(
        self,
        file_content: bytes,
        file_name: str,
        use_ai_description: bool = False
    ) -> ConversionResult:
        """Convert document to Markdown"""
        import time
        start_time = time.time()
        
        # Determine file type from extension
        file_ext = Path(file_name).suffix.lower()
        
        # Create a temporary file for MarkItDown
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext
        ) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Perform conversion
            if use_ai_description and self.llm_client:
                result = self.markitdown.convert(
                    tmp_path,
                    llm_client=self.llm_client,
                    llm_model=self.llm_model
                )
            else:
                result = self.markitdown.convert(tmp_path)
            
            duration = time.time() - start_time
            
            return ConversionResult(
                text_content=result.text_content,
                file_name=file_name,
                file_type=file_ext.lstrip("."),
                file_size=len(file_content),
                duration=duration,
                markdown_length=len(result.text_content),
                metadata={
                    "source": "markitdown",
                    "converted_at": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            raise
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    async def convert_stream(
        self,
        file_stream: BinaryIO,
        file_name: str,
        use_ai_description: bool = False
    ) -> ConversionResult:
        """Convert document from a stream"""
        file_content = file_stream.read()
        return await self.convert(file_content, file_name, use_ai_description)
    
    async def summarize(
        self,
        markdown_content: str,
        file_name: str
    ) -> AISummaryResult:
        """Generate AI summary of the markdown content"""
        if not self.llm_client:
            # Return default summary if no LLM client
            words = len(markdown_content.split())
            reading_time = max(1, words // 200)  # ~200 words per minute
            
            return AISummaryResult(
                summary=f"Document converted from {file_name}. Contains {words} words.",
                key_points=[
                    f"Converted from {file_name}",
                    f"Total words: {words}",
                    f"Estimated reading time: {reading_time} minutes"
                ],
                document_type="Document",
                tags=["converted", "markdown"],
                reading_time=reading_time
            )
        
        # Prompt for summarization
        prompt = f"""Analyze the following document and provide:
1. A one-line summary (summary)
2. 3-5 key points (key_points)
3. Document type classification (document_type) - e.g., Report, Invoice, Contract, Article, etc.
4. 2-4 relevant tags (tags)

Document: {file_name}

Content:
{markdown_content[:8000]}

Respond in JSON format:
{{
    "summary": "...",
    "key_points": ["...", "..."],
    "document_type": "...",
    "tags": ["...", "..."]
}}
"""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a document analysis assistant. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Parse JSON response
            data = json.loads(content)
            
            # Estimate reading time
            words = len(markdown_content.split())
            reading_time = max(1, words // 200)
            
            return AISummaryResult(
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                document_type=data.get("document_type", "Document"),
                tags=data.get("tags", ["markdown"]),
                reading_time=reading_time,
                tokens_used=tokens_used
            )
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            # Fallback to basic summary
            words = len(markdown_content.split())
            reading_time = max(1, words // 200)
            
            return AISummaryResult(
                summary=f"Converted document with {words} words",
                key_points=[f"Source: {file_name}", f"Word count: {words}"],
                document_type="Document",
                tags=["converted"],
                reading_time=reading_time
            )


# Singleton instance
document_service = DocumentService()