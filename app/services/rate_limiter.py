"""
Rate limiting and usage tracking
"""
from typing import Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from app.core.config import settings
from loguru import logger


class UsageTracker:
    """Track API usage for rate limiting and billing"""
    
    def __init__(self):
        self._conversions: Dict[str, int] = defaultdict(int)
        self._tokens: Dict[str, int] = defaultdict(int)
        self._files: Dict[str, int] = defaultdict(int)
        self._format_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_reset: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def record_conversion(
        self,
        api_key: str,
        file_type: str,
        tokens_used: int = 0
    ):
        """Record a conversion for usage tracking"""
        async with self._lock:
            self._conversions[api_key] += 1
            self._tokens[api_key] += tokens_used
            self._files[api_key] += 1
            self._format_counts[api_key][file_type] += 1
            self._last_reset[api_key] = datetime.utcnow()
    
    async def get_usage(self, api_key: str) -> Dict:
        """Get usage statistics for an API key"""
        return {
            "total_conversions": self._conversions.get(api_key, 0),
            "total_tokens": self._tokens.get(api_key, 0),
            "total_files": self._files.get(api_key, 0),
            "by_format": dict(self._format_counts.get(api_key, {})),
            "period_start": self._last_reset.get(api_key, datetime.utcnow()).isoformat()
        }
    
    async def check_rate_limit(
        self,
        api_key: str,
        limit: int = 100,
        period_seconds: int = 3600
    ) -> tuple[bool, Optional[str]]:
        """Check if API key has exceeded rate limit"""
        async with self._lock:
            count = self._conversions.get(api_key, 0)
            last_reset = self._last_reset.get(api_key)
            
            if last_reset:
                elapsed = (datetime.utcnow() - last_reset).total_seconds()
                if elapsed > period_seconds:
                    # Reset counter
                    self._conversions[api_key] = 0
                    count = 0
            
            if count >= limit:
                return False, f"Rate limit exceeded: {limit} requests per {period_seconds}s"
            
            return True, None


# Singleton instance
usage_tracker = UsageTracker()
