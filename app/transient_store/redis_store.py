import redis
from typing import Optional, Any
import json
from datetime import timedelta
import os
import logging

logger = logging.getLogger(__name__)

class RedisStore:
    """A secure Redis-based store with TTL"""
    
    def __init__(self, namespace: str = "default", time_delta: int = 60):
        """
        Initialize the store
        
        Args:
            namespace (str): Namespace for the default store (prefix for Redis keys)
        """
        redis_host = os.getenv("REDIS_HOST", "redis")  # Default to service name if env var not set
        redis_port = os.getenv("REDIS_PORT", 6379)     # Default Redis port
        
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,  # default db
            decode_responses=True
        )
        self.namespace = namespace
        self.default_ttl = timedelta(minutes=time_delta)
    
    def _get_key(self, key: str) -> str:
        """Generate namespaced key"""
        return f"{self.namespace}:{key}"
    
    def set_value(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store a key, value with TTL
        
        Args:
            key (str):  key
            value (Any):  value (will be JSON serialized)
            ttl (Optional[int]): Time to live in seconds (default: 5 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            redis_key = self._get_key(key)
            
            # Serialize value if not string
            if not isinstance(value, str):
                value = json.dumps(value)
            
            # Set value with TTL
            ttl = ttl if ttl is not None else int(self.default_ttl.total_seconds())
            success = self.redis_client.setex(
                name=redis_key,
                time=ttl,
                value=value
            )
            
            if success:
                logger.debug(f"Value stored successfully: {redis_key}")
            else:
                logger.error(f"Failed to store value: {redis_key}")
                
            return success
        
        except Exception as e:
            logger.error(f"Error storing value for {key}: {str(e)}")
            return False
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value
        
        Args:
            key (str): key
            default (Any): Default value if key doesn't exist
            
        Returns:
            Any: value or default if not found
        """
        try:
            redis_key = self._get_key(key)
            value = self.redis_client.get(redis_key)
            
            if value is None:
                return default
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error(f"Error retrieving value {key}: {str(e)}")
            return default

    def get_keys_by_pattern(self, pattern: str) -> Any:
        """
        Retrieve a value by pattern
        
        Args:
            pattern (str): pattern
            
        Returns:
            Any: value or default if not found
        """
        try:
            return self.redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Error retrieving value by pattern {pattern}: {str(e)}")
            return []
        
    def delete_key(self, key: str) -> bool:
        """
        Delete a key, value pair
        
        Args:
            key (str): key
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            redis_key = self._get_key(key)
            return bool(self.redis_client.delete(redis_key))
        except Exception as e:
            logger.error(f"Error deleting key {key}: {str(e)}")
            return False
    

    def extend_ttl(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Extend the TTL of a key
        
        Args:
            key (str):  key
            ttl (Optional[int]): New TTL in seconds (default: 5 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            redis_key = self._get_key(key)
            ttl = ttl if ttl is not None else int(self.default_ttl.total_seconds())
            return bool(self.redis_client.expire(redis_key, ttl))
        except Exception as e:
            logger.error(f"Error extending TTL for key {key}: {str(e)}")
            return False

# Create global instance
redis_store = RedisStore()