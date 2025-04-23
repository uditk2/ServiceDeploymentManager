import redis
from typing import Optional, Any
import json
from datetime import timedelta
import os
import logging

logger = logging.getLogger(__name__)

class RedisSecretsStore:
    """A secure Redis-based secrets store with TTL"""
    
    def __init__(self, namespace: str = "secrets"):
        """
        Initialize the secrets store
        
        Args:
            namespace (str): Namespace for the secrets (prefix for Redis keys)
        """
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv("REDIS_PORT"),
            db=1,  # Use a separate DB for secrets
            decode_responses=True
        )
        self.namespace = namespace
        self.default_ttl = timedelta(minutes=60)
    
    def _get_key(self, key: str) -> str:
        """Generate namespaced key"""
        return f"{self.namespace}:{key}"
    
    def set_secret(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store a secret with TTL
        
        Args:
            key (str): Secret key
            value (Any): Secret value (will be JSON serialized)
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
                logger.debug(f"Secret stored successfully: {redis_key}")
            else:
                logger.error(f"Failed to store secret: {redis_key}")
                
            return success
        
        except Exception as e:
            logger.error(f"Error storing secret {key}: {str(e)}")
            return False
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a secret
        
        Args:
            key (str): Secret key
            default (Any): Default value if key doesn't exist
            
        Returns:
            Any: Secret value or default if not found
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
            logger.error(f"Error retrieving secret {key}: {str(e)}")
            return default

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret
        
        Args:
            key (str): Secret key
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            redis_key = self._get_key(key)
            return bool(self.redis_client.delete(redis_key))
        except Exception as e:
            logger.error(f"Error deleting secret {key}: {str(e)}")
            return False
    

    def extend_ttl(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Extend the TTL of a secret
        
        Args:
            key (str): Secret key
            ttl (Optional[int]): New TTL in seconds (default: 5 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            redis_key = self._get_key(key)
            ttl = ttl if ttl is not None else int(self.default_ttl.total_seconds())
            return bool(self.redis_client.expire(redis_key, ttl))
        except Exception as e:
            logger.error(f"Error extending TTL for secret {key}: {str(e)}")
            return False

# Create global instance
secrets_store = RedisSecretsStore()