class ToolManager:
    def __init__(self):
        self.tools = {}
        self.requires_approval = set()
    def register(self, name: str, func, requires_approval: bool = False):
        self.tools[name] = func
        if requires_approval:
            self.requires_approval.add(name)
    def invoke(self, name: str, *args, **kwargs):
        if name not in self.tools:
            raise KeyError(f"Unknown tool {name}")
        return self.tools[name](*args, **kwargs)
