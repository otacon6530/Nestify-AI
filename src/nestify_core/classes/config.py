from __future__ import annotations
from ..functions.config_load import load_config


class Config:
    def __init__(self):
        # Bind functions
        self.load = load_config
        self.data: dict = self.load()

    def get(self, *path, default=None):
        node = self.data
        for key in path:
            if not isinstance(node, dict):
                return default
            node = node.get(key)
        return node if node is not None else default
