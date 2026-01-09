class Memory:
    def __init__(self):
        self._items = []
        self.add = lambda text, metadata=None: self._items.append((text, metadata))
        self.search = lambda query, top_k=5: [t for t, _ in self._items][:top_k]
