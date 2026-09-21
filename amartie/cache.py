"""
LMCache Integration for AMARTIE JEV Gate
=========================================
Caches judge evaluations to avoid redundant computation.
From Code Unpacked video: 13x faster when KV cache shared.

In AMARTIE: same 9 judges evaluate similar actions repeatedly.
Cache key = hash of action_type + action_payload.
Cache TTL = configurable (default: 1 hour).
"""

import hashlib
import json
import os
import time
from typing import Dict, List, Optional, Tuple


class JudgeCache:
    """
    LMCache-style evaluation cache for JEV judge results.
    
    Caches the entire 9-judge verdict set for an action.
    Subsequent identical/similar actions pull from cache.
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 1000):
        """
        Initialize the judge cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 1 hour)
            max_entries: Maximum number of cached evaluations
        """
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, dict] = {}  # key -> {"verdicts": [...], "timestamp": ...}
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, action_type: str, payload: dict) -> str:
        """Generate cache key from action."""
        content = json.dumps({
            "action_type": action_type,
            "payload": payload
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get(self, action_type: str, payload: dict) -> Optional[List[dict]]:
        """
        Get cached verdicts for an action.
        
        Returns None if cache miss or expired.
        """
        key = self._make_key(action_type, payload)
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        # Check TTL
        if time.time() - entry["timestamp"] > self.ttl:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry["verdicts"]
    
    def put(self, action_type: str, payload: dict, verdicts: List[dict]):
        """Cache verdicts for an action."""
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_entries:
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
        
        key = self._make_key(action_type, payload)
        self._cache[key] = {
            "verdicts": verdicts,
            "timestamp": time.time()
        }
    
    def invalidate(self, action_type: str, payload: dict):
        """Invalidate a specific cache entry."""
        key = self._make_key(action_type, payload)
        self._cache.pop(key, None)
    
    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    @property
    def stats(self) -> dict:
        """Cache statistics."""
        total = self._hits + self._misses
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


# Singleton cache instance
judge_cache = JudgeCache(
    ttl_seconds=int(os.environ.get("JUDGE_CACHE_TTL", "3600")),
    max_entries=int(os.environ.get("JUDGE_CACHE_MAX", "1000"))
)
