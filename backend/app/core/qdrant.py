from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)
from typing import List, Dict, Any, Optional
import uuid

from .config import settings


class QdrantManager:
    """Manages Qdrant vector database for RAG."""

    COLLECTION_RESEARCH = "research_context"
    COLLECTION_PRD = "prd_features"
    COLLECTION_PAST_PROJECTS = "past_projects"

    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
        )
        self._init_collections()

    def _init_collections(self):
        """Initialize collections if they don't exist."""
        collections = [c.name for c in self.client.get_collections().collections]

        if self.COLLECTION_RESEARCH not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION_RESEARCH,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

        if self.COLLECTION_PRD not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION_PRD,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

        if self.COLLECTION_PAST_PROJECTS not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION_PAST_PROJECTS,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

    async def store_research_embeddings(
        self, run_id: str, chunks: List[str], vectors: List[List[float]]
    ) -> List[str]:
        """Store research chunks with embeddings."""
        ids = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = str(uuid.uuid4())
            ids.append(point_id)
            self.client.upsert(
                collection_name=self.COLLECTION_RESEARCH,
                points=[
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": {"run_id": run_id, "chunk_index": i, "text": chunk},
                    }
                ],
            )
        return ids

    async def store_prd_embeddings(
        self,
        run_id: str,
        user_stories: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> List[str]:
        """Store PRD user stories with embeddings."""
        ids = []
        for i, (story, vector) in enumerate(zip(user_stories, vectors)):
            point_id = str(uuid.uuid4())
            ids.append(point_id)
            self.client.upsert(
                collection_name=self.COLLECTION_PRD,
                points=[
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "run_id": run_id,
                            "story_index": i,
                            "story_id": story.get("id", f"US-{i:03d}"),
                            "text": f"{story.get('persona', '')} {story.get('action', '')} {story.get('outcome', '')}",
                        },
                    }
                ],
            )
        return ids

    async def retrieve_research_context(
        self, query: str, query_vector: List[float], run_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant research context for a query."""
        results = self.client.search(
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

    async def retrieve_prd_context(
        self, query: str, query_vector: List[float], run_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant PRD context (user stories) for traceability."""
        results = self.client.search(
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

    def get_collection_points(self, collection_name: str, run_id: str) -> int:
        """Get count of points for a run in a collection."""
        results = self.client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="run_id", match=MatchValue(value=run_id))]
            ),
            limit=1,
        )
        return results[1] if len(results) > 1 else 0


qdrant_manager = QdrantManager()
