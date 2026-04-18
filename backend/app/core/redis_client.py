import redis.asyncio as redis
from .config import settings
import logging

logger = logging.getLogger(__name__)

async def get_redis():
    try:
        r = redis.from_url(
            settings.REDIS_URL, 
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True
        )
        return r
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise
