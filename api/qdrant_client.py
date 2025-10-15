import os
from typing import Optional, List, Dict, Any

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:
    QdrantClient = None  # Optional dependency
    rest = None


class QdrantService:
    """Optional Qdrant client scaffold for future vector features."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.client = None
        if QdrantClient is not None:
            try:
                self.client = QdrantClient(url=self.url)
            except Exception:
                self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def ensure_collection(self, name: str, vector_size: int = 384) -> bool:
        if not self.client:
            return False
        try:
            if name not in [c.name for c in self.client.get_collections().collections]:
                self.client.recreate_collection(
                    collection_name=name,
                    vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
                )
            return True
        except Exception:
            return False

    def upsert_points(self, collection: str, vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        if not self.client:
            return False
        try:
            points = []
            for idx, (vec, payload) in enumerate(zip(vectors, payloads)):
                points.append(rest.PointStruct(id=payload.get("id", idx), vector=vec, payload=payload))
            self.client.upsert(collection_name=collection, points=points)
            return True
        except Exception:
            return False


