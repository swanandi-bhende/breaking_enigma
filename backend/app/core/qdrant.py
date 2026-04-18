from qdrant_client import AsyncQdrantClient
from .config import settings
import logging

logger = logging.getLogger(__name__)

def get_qdrant_client():
    try:
        kwargs = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
            
        client = AsyncQdrantClient(**kwargs)
        return client
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        raise
