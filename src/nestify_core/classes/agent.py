

import importlib.util
import os

class Agent:
    """
    Agent class for orchestrating LLM reasoning, tool use, and memory.
    Supports loading agent subclasses from the agents folder by name.
    """
    def __init__(self):
        self.system_prompt = "You are Nestify Agent"

    @staticmethod
    def load_agent(agent_name, agents_dir="agents"):
        """
        Dynamically import and instantiate an agent subclass from the agents folder by name.
        Args:
            agent_name: The agent profile name (str, e.g., 'default').
            agents_dir: Directory containing agent Python files (default 'agents').
        Returns:
            An instance of the agent subclass.
        Raises:
            ImportError, AttributeError, FileNotFoundError
        """
        module_path = os.path.join(agents_dir, f"{agent_name}.py")
        if not os.path.exists(module_path):
            raise FileNotFoundError(f"Agent class file not found: {module_path}")
        spec = importlib.util.spec_from_file_location(f"agents.{agent_name}", module_path)
        if spec is None:
            raise ImportError(f"Could not load spec for agent: {agent_name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # By convention, agent class should be named <Name>Agent (e.g., DefaultAgent)
        class_name = f"{agent_name.capitalize()}Agent"
        if not hasattr(module, class_name):
            raise AttributeError(f"Agent class '{class_name}' not found in {module_path}")
        agent_cls = getattr(module, class_name)
        return agent_cls()

    def prepare_context(self, task: str, config, memory):
        return {"prompt": task, "config": config, "memory": memory}
