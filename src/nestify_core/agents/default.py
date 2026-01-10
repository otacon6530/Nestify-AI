from src.nestify_core.classes.agent_base import Agent

class DefaultAgent(Agent):
    """
    Default agent profile. Override methods to customize behavior.
    """
    def get_name(self):
        return "default"

    def get_prompt_template(self):
        return "You are a helpful AI assistant."

    # You can override more methods as needed
