class SkillsManager:
    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.skills = {}
    def register_shell(self, func):
        self.skills["shell"] = func
