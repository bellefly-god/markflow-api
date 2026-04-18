"""
Batch conversion service with task queue
"""
import os
import io
import json
import uuid
import time
import asyncio
import zipfile
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from app.services.converter import document_service
from app.core.config import settings
from loguru import logger


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConversionTask:
    """Single file conversion task"""
    task_id: str
    file_name: str
    file_content: bytes
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class BatchJob:
    """Batch conversion job"""
    job_id: str
    tasks: List[ConversionTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0


class BatchService:
    """Batch conversion service with queue"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.jobs: Dict[str, BatchJob] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running = False
    
    async def start(self):
        """Start the worker pool"""
        if self._running:
            return
        
        self._running = True
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        logger.info(f"Batch service started with {self.max_concurrent} workers")
    
    async def stop(self):
        """Stop the worker pool"""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
        logger.info("Batch service stopped")
    
    async def _worker(self, worker_id: int):
        """Worker coroutine for processing tasks"""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get task from queue
                job_id, task = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                
                # Process the task
                await self._process_task(job_id, task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_task(self, job_id: str, task: ConversionTask):
        """Process a single conversion task"""
        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        
        try:
            # Perform conversion
            result = await document_service.convert(
                file_content=task.file_content,
                file_name=task.file_name
            )
            
            task.result = result.to_dict()
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
            # Update job stats
            job = self.jobs.get(job_id)
            if job:
                job.completed_files += 1
                await self._check_job_completion(job_id)
            
            logger.info(f"Task {task.task_id} completed: {task.file_name}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            
            job = self.jobs.get(job_id)
            if job:
                job.failed_files += 1
                await self._check_job_completion(job_id)
            
            logger.error(f"Task {task.task_id} failed: {e}")
    
    async def _check_job_completion(self, job_id: str):
        """Check if job is complete"""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        # Check if all tasks are done
        all_done = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            for t in job.tasks
        )
        
        if all_done:
            job.status = TaskStatus.COMPLETED
            job.completed_at = time.time()
            logger.info(f"Job {job_id} completed: {job.completed_files}/{job.total_files} files")
    
    async def create_job(self, files: List[tuple]) -> str:
        """
        Create a new batch job
        
        Args:
            files: List of (file_name, file_content) tuples
        
        Returns:
            job_id
        """
        job_id = f"batch-{uuid.uuid4().hex[:12]}"
        
        # Create tasks
        tasks = []
        for file_name, file_content in files:
            task = ConversionTask(
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                file_name=file_name,
                file_content=file_content
            )
            tasks.append(task)
        
        # Create job
        job = BatchJob(
            job_id=job_id,
            tasks=tasks,
            total_files=len(tasks)
        )
        self.jobs[job_id] = job
        
        # Ensure workers are running
        await self.start()
        
        # Queue all tasks
        for task in tasks:
            await self._queue.put((job_id, task))
        
        job.status = TaskStatus.PROCESSING
        job.started_at = time.time()
        
        logger.info(f"Created batch job {job_id} with {len(tasks)} files")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "total_files": job.total_files,
            "completed_files": job.completed_files,
            "failed_files": job.failed_files,
            "progress": job.completed_files / job.total_files if job.total_files > 0 else 0,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "file_name": t.file_name,
                    "status": t.status.value,
                    "error": t.error
                }
                for t in job.tasks
            ]
        }
    
    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job results (completed conversions)"""
        job = self.jobs.get(job_id)
        if not job or job.status != TaskStatus.COMPLETED:
            return None
        
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "total_files": job.total_files,
            "completed_files": job.completed_files,
            "failed_files": job.failed_files,
            "results": [
                {
                    "file_name": t.file_name,
                    "success": t.status == TaskStatus.COMPLETED,
                    "markdown": t.result.get("text_content") if t.result else None,
                    "error": t.error
                }
                for t in job.tasks
            ]
        }
    
    def generate_zip(self, job_id: str) -> Optional[bytes]:
        """Generate a ZIP file with all converted markdown files"""
        job = self.jobs.get(job_id)
        if not job or job.status != TaskStatus.COMPLETED:
            return None
        
        # Create in-memory ZIP
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for task in job.tasks:
                if task.status == TaskStatus.COMPLETED and task.result:
                    # Convert filename to .md
                    base_name = Path(task.file_name).stem
                    md_name = f"{base_name}.md"
                    
                    # Add to ZIP
                    zf.writestr(md_name, task.result.get("text_content", ""))
            
            # Add summary file
            summary = {
                "job_id": job.job_id,
                "created_at": datetime.utcnow().isoformat(),
                "total_files": job.total_files,
                "completed_files": job.completed_files,
                "failed_files": job.failed_files,
                "files": [
                    {
                        "original": t.file_name,
                        "converted": f"{Path(t.file_name).stem}.md",
                        "status": t.status.value
                    }
                    for t in job.tasks
                ]
            }
            zf.writestr("_summary.json", json.dumps(summary, indent=2))
        
        return zip_buffer.getvalue()
    
    def cleanup_job(self, job_id: str):
        """Remove job from memory"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Cleaned up job {job_id}")


# Singleton instance
batch_service = BatchService(max_concurrent=3)
