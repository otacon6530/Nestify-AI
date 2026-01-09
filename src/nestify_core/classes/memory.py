from datetime import datetime
import math

class Memory:
    """
    Memory class for storing and retrieving text/code snippets with optional semantic search.

    If an embedding function is provided, supports vector-based similarity search.
    Otherwise, falls back to keyword search.
    Each entry includes text, metadata, timestamp, and (optionally) embedding.
    """
    def __init__(self, embed_fn=None):
        """
        Initialize memory.
        Args:
            embed_fn: function(text) -> vector, or None for keyword-only mode.
        """
        self._items = []  # Each item: dict with text, embedding, metadata, timestamp
        self._embed_fn = embed_fn

    def add(self, text, metadata=None):
        """
        Add a new memory entry.
        Args:
            text: The text or code snippet to store.
            metadata: Optional dict of metadata (e.g., source, tags).
        """
        item = {
            "text": text,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow()
        }
        if self._embed_fn:
            item["embedding"] = self._embed_fn(text)
        self._items.append(item)

    def search(self, query, top_k=5):
        """
        Search memory for relevant entries.
        Args:
            query: The search query (text or code).
            top_k: Number of top results to return.
        Returns:
            List of matching memory items (dicts).
        """
        if self._embed_fn:
            query_vec = self._embed_fn(query)
            def cosine(a, b):
                """Compute cosine similarity between two vectors."""
                dot = sum(x*y for x, y in zip(a, b))
                norm_a = math.sqrt(sum(x*x for x in a))
                norm_b = math.sqrt(sum(y*y for y in b))
                return dot / (norm_a * norm_b + 1e-8)
            scored = [
                (item, cosine(query_vec, item["embedding"]))
                for item in self._items if "embedding" in item
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [item for item, _ in scored[:top_k]]
        else:
            # Fallback: keyword search
            results = [item for item in self._items if query.lower() in item["text"].lower()]
            return results[:top_k]
