import os
import yaml

class AgentConfigLoader:
    """
    Loads agent configuration files from the agents directory by agent name.
    Supports YAML format for agent profiles.
    """
    def __init__(self, agents_dir):
        self.agents_dir = agents_dir

    def load(self, agent_name):
        """
        Load the configuration for the given agent name.
        Args:
            agent_name: The name of the agent profile to load.
        Returns:
            config (dict): The loaded configuration dictionary.
        Raises:
            FileNotFoundError: If the agent config file does not exist.
            yaml.YAMLError: If the config file is invalid YAML.
        """
        config_path = os.path.join(self.agents_dir, f"{agent_name}.yml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Agent config not found: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
