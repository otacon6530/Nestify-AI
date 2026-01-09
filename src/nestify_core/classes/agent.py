class Agent:
    def __init__(self):
        self.system_prompt = "You are Nestify Agent"
    def prepare_context(self, task: str, config, memory):
        return {"prompt": task, "config": config, "memory": memory}
