from datetime import datetime
import math

class Memory:

    """
    Memory class for storing and retrieving text/code snippets with optional semantic search.

    If an embedding function is provided, supports vector-based similarity search.
    Otherwise, falls back to keyword search.
    Each entry includes text, metadata, timestamp, and (optionally) embedding.

    ---
    Working Memory Buffer:
    ---------------------
    This class also provides a temporary, non-persistent "working memory" buffer for multi-step LLM reasoning.
    - Working memory is NOT included in normal memory search/history and is NOT persisted.
    - It is intended for storing a rolling context (e.g., intermediate responses, tool results) during a single multi-step response.
    - Use add_working() to append, get_working() to retrieve (optionally clear), and clear_working() to reset the buffer.
    - Working memory is cleared between requests or when a multi-step response is complete.
    """
    def __init__(self, embed_fn=None):
        """
        Initialize memory.
        Args:
            embed_fn: function(text) -> vector, or None for keyword-only mode.
        """
        self._items = []  # Each item: dict with text, embedding, metadata, timestamp
        self._embed_fn = embed_fn
        self._working_memory = []  # Temporary buffer for multi-step LLM reasoning

    def add_working(self, text):
        """
        Append a string to the working memory buffer.
        Args:
            text: The string (e.g., intermediate response, tool result) to append.
        Note:
            Working memory is temporary and not persisted. Use for multi-step LLM reasoning only.
        """
        self._working_memory.append(text)

    def get_working(self, clear=False):
        """
        Retrieve the current working memory buffer as a single string.
        Args:
            clear: If True, clear the buffer after retrieval (default False).
        Returns:
            The concatenated working memory string (or empty string if buffer is empty).
        """
        result = "\n".join(self._working_memory)
        if clear:
            self.clear_working()
        return result

    def clear_working(self):
        """
        Clear the working memory buffer.
        Use this to reset temporary context between multi-step LLM responses.
        """
        self._working_memory = []

    def latest(self, count=5):
        """
        Return the latest `count` memory records, most recent last.
        Args:
            count: Number of records to return (default 5).
        Returns:
            List of memory items (dicts), ordered oldest to newest.
        """
        return self._items[-count:] if count > 0 else []
    
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
            embedding = self._embed_fn(text)
            if embedding is not None:
                item["embedding"] = embedding
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
            if query_vec is None:
                query_vec = None
            else:
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
        # Fallback: keyword search with simple token overlap scoring
        query_terms = {token for token in query.lower().split() if len(token) > 2}
        scored_results = []
        for item in self._items:
            text_lower = item["text"].lower()
            if query_terms:
                item_terms = {token for token in text_lower.split() if len(token) > 2}
                overlap = len(query_terms & item_terms)
                if overlap > 0:
                    scored_results.append((item, overlap))
                elif query.lower() in text_lower:
                    scored_results.append((item, 1))
            elif query.lower() in text_lower:
                scored_results.append((item, 1))
        scored_results.sort(key=lambda pair: pair[1], reverse=True)
        return [item for item, _ in scored_results[:top_k]]
