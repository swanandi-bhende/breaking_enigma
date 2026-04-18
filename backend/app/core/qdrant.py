"""
Qdrant vector database manager for ADWF.
Lazy-initialised — safe to import even when Qdrant is unreachable.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional

from .config import settings

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manages Qdrant vector database for RAG. Lazy-connects on first use."""

    COLLECTION_RESEARCH = "research_context"
    COLLECTION_PRD = "prd_features"
    COLLECTION_PAST_PROJECTS = "past_projects"

    def __init__(self):
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Return (and lazily create) the Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                )
                self._ensure_collections()
                self._initialized = True
            except Exception as e:
                logger.warning(f"Qdrant lazy-init failed: {e}. Vector storage will be skipped.")
                self._client = None
        return self._client

    def _ensure_collections(self):
        """Create collections if they don't exist. Called once on first connection."""
        if not self._client:
            return
        try:
            from qdrant_client.models import Distance, VectorParams
            existing = [c.name for c in self._client.get_collections().collections]

            for name in [self.COLLECTION_RESEARCH, self.COLLECTION_PRD, self.COLLECTION_PAST_PROJECTS]:
                if name not in existing:
                    self._client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
                    )
                    logger.info(f"Created Qdrant collection: {name}")
        except Exception as e:
            logger.warning(f"Failed to ensure Qdrant collections: {e}")

    async def store_research_embeddings(
        self, run_id: str, chunks: List[str], vectors: List[List[float]]
    ) -> List[str]:
        """Store research chunks with embeddings. Returns list of point IDs."""
        client = self._get_client()
        if not client:
            return []
        try:
            ids = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                point_id = str(uuid.uuid4())
                ids.append(point_id)
                client.upsert(
                    collection_name=self.COLLECTION_RESEARCH,
                    points=[{
                        "id": point_id,
                        "vector": vector,
                        "payload": {"run_id": run_id, "chunk_index": i, "text": chunk},
                    }],
                )
            return ids
        except Exception as e:
            logger.warning(f"Failed to store research embeddings: {e}")
            return []

    async def store_prd_embeddings(
        self,
        run_id: str,
        user_stories: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> List[str]:
        """Store PRD user stories with embeddings."""
        client = self._get_client()
        if not client:
            return []
        try:
            ids = []
            for i, (story, vector) in enumerate(zip(user_stories, vectors)):
                point_id = str(uuid.uuid4())
                ids.append(point_id)
                client.upsert(
                    collection_name=self.COLLECTION_PRD,
                    points=[{
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "run_id": run_id,
                            "story_index": i,
                            "story_id": story.get("id", f"US-{i:03d}"),
                            "text": f"{story.get('persona', '')} {story.get('action', '')} {story.get('outcome', '')}",
                        },
                    }],
                )
            return ids
        except Exception as e:
            logger.warning(f"Failed to store PRD embeddings: {e}")
            return []

    async def retrieve_research_context(
        self, query: str, query_vector: List[float], run_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant research context for a query."""
        client = self._get_client()
        if not client:
            return []
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = client.search(
                collection_name=self.COLLECTION_RESEARCH,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="run_id", match=MatchValue(value=run_id))]
                ),
                limit=limit,
            )
            return [
                {
                    "id": r.id,
                    "text": r.payload["text"],
                    "score": r.score,
                    "chunk_index": r.payload.get("chunk_index"),
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Failed to retrieve research context: {e}")
            return []

    async def retrieve_prd_context(
        self, query: str, query_vector: List[float], run_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant PRD context (user stories) for traceability."""
        client = self._get_client()
        if not client:
            return []
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = client.search(
                collection_name=self.COLLECTION_PRD,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="run_id", match=MatchValue(value=run_id))]
                ),
                limit=limit,
            )
            return [
                {
                    "id": r.id,
                    "story_id": r.payload.get("story_id"),
                    "text": r.payload.get("text"),
                    "score": r.score,
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Failed to retrieve PRD context: {e}")
            return []


qdrant_manager = QdrantManager()
