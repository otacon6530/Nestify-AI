from __future__ import annotations
from ..functions.arg_parse import parse as parse_args


class ArgManager:
    def __init__(self):
        self.parse = parse_args
