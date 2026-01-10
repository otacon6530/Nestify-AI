

import importlib.util
import os
import json

class Agent:
    """
    Agent class for orchestrating LLM reasoning, tool use, and memory.
    Supports loading agent subclasses from the agents folder by name.
    """
    def __init__(self, memory, tool_manager, llm):
        self.system_prompt = "You are Nestify Agent"
        self.memory = memory
        self.tool_manager = tool_manager
        self.llm = llm

    @staticmethod
    def load_agent(agent_name, agents_dir=None):
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
        # Default agents directory to src/nestify_core/agents next to this package
        if agents_dir is None:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            agents_dir = os.path.join(base_dir, "agents")
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

    def getMemory(self, text: str):
        context_text = ""
        context_items = self.memory.search(text, top_k=3)
        if context_items:
            context_text += f"Relevant notes:\n"
            context_text += "\n---\n".join(
                f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in context_items
            )
        latest_mem = self.memory.latest(5)
        if latest_mem:
            context_text += f"[Troubleshooting] Latest memory records:\n"
            context_text += "\n---\n".join(
                f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in latest_mem
            )
        return context_text
    def getTools(self, text: str):
        tool_lines = [f"{tool['name']}: {tool['description']}" for tool in self.tool_manager.list_tools()]
        tools_text = ""
        if tool_lines:
            tools_text += "\n---\n"
            tools_text += "\n".join(tool_lines)
        return tools_text
    def getResponse(self, prompt: str, **kwargs):
        stream = kwargs.get("stream", False)
        return_value = None
        if stream:
            # Streaming: accumulate tokens and yield as they arrive, then store full response at end
            response_text = ""
            for event in self.llm.generate(prompt, **kwargs):
                if isinstance(event, dict):
                    if event.get("type") == "token":
                        response_text += event.get("value", "")
                        yield event
                    elif event.get("type") == "final":
                        # Prefer full text from final event if present
                        return_value = event.get("result", {}).get("text", response_text)
                        yield event
        else:
            # Non-streaming: store output immediately
            result = self.llm.generate(prompt, **kwargs)
            return_value = result.get("output") or result.get("text")
        return return_value
    def generate(self, text: str, tool_manager, logger, **kwargs):
        """
        Generate a response from the LLM, optionally including memory context.
        All dependencies are passed in as arguments to keep Agent stateless.
        Supports streaming or non-streaming outputs.
        """
        context_text = self.getMemory(text)
        self.memory.add(text, metadata={"source": "user"})
        context_text += self.getTools(text)
        
        prompt = (
            "You are continuing a conversation. Use the relevant notes below "
            "to answer the latest user message.\n\n"
            f"{context_text}\n\n"
            f"Latest user message: {text}"
        )

        logger.log("DEBUG", "Final prompt constructed", prompt=prompt)

        stream = kwargs.get("stream", False)
        response = None
        if stream:
            # Streaming: accumulate tokens and yield as they arrive, then store full response at end
            response_text = ""
            for event in self.llm.generate(prompt, **kwargs):
                if isinstance(event, dict):
                    if event.get("type") == "token":
                        response_text += event.get("value", "")
                        yield event
                    elif event.get("type") == "final":
                        # Prefer full text from final event if present
                        response = event.get("result", {}).get("text", response_text)
                        yield event
        else:
            # Non-streaming: store output immediately
            result = self.llm.generate(prompt, **kwargs)
            response = result.get("output") or result.get("text")
        
        if response:
            logger.log("DEBUG", "LLM response received", response=response)
            # Try to extract tool calls from the response
            tool_call = tool_manager.extract_tool_call(response)
            if tool_call == "" :
                self.memory.add(response, metadata={"source": "assistant"})
            else:
                self.memory.add(tool_call, metadata={"source": "tool"})
        return response
