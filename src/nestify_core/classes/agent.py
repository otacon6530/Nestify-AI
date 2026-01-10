
from .agent_config_loader import AgentConfigLoader

class Agent:
    """
    Agent class for orchestrating LLM reasoning, tool use, and memory.
    Supports loading agent-specific configuration profiles from the agents folder.
    """
    def __init__(self):
        self.system_prompt = "You are Nestify Agent"

    def load_config(self, agent_name, agents_dir="agents"):
        """
        Load the configuration for a given agent name from the agents directory.
        Args:
            agent_name: The agent profile name (str).
            agents_dir: Directory containing agent config files (default 'agents').
        Returns:
            config (dict): The loaded agent configuration.
        Raises:
            FileNotFoundError, yaml.YAMLError
        """
        loader = AgentConfigLoader(agents_dir)
        return loader.load(agent_name)

    def prepare_context(self, task: str, config, memory):
        return {"prompt": task, "config": config, "memory": memory}
