

import importlib.util
import os
import json

class Agent:
    """
    Agent class for orchestrating LLM reasoning, tool use, and memory.
    Supports loading agent subclasses from the agents folder by name.
    """
    def __init__(self, memory, tool_manager, llm, logger):
        self.system_prompt = "You are Nestify Agent"
        self.memory = memory
        self.tool_manager = tool_manager
        self.llm = llm
        self.logger = logger

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
    def generate(self, text: str, actions=None, max_steps=8, summarize=True, **kwargs):
        """
        Multi-step LLM/tool chaining: recursively handle tool calls, accumulate actions, and summarize at the end.
        Args:
            text: User message
            actions: List to accumulate (tool calls, LLM responses)
            max_steps: Max recursion depth
            summarize: If True, summarize all actions at the end
            kwargs: stream, etc.
        Returns:
            Final summary (or generator if streaming)
        """
        if actions is None:
            actions = []
        if max_steps <= 0:
            # Prevent infinite loops
            actions.append({"type": "error", "message": "Max steps exceeded."})
            summarize_kwargs = dict(kwargs)
            stream_val = summarize_kwargs.pop('stream', False)
            return self._summarize_actions(text, actions, stream=stream_val, **summarize_kwargs)

        context_text = self.getMemory(text)
        self.memory.add(text, metadata={"source": "user"})
        context_text += self.getTools(text)

        prompt = (
            "You are continuing a conversation. Use the relevant notes below "
            "to answer the latest user message.\n\n"
            f"{context_text}\n\n"
            f"Latest user message: {text}"
        )

        self.logger.log("DEBUG", "Final prompt constructed", prompt=prompt)

        stream = kwargs.get("stream", False)
        response = None
        if stream:
            # Streaming: accumulate tokens, yield as they arrive, then process final
            response_text = ""
            for event in self.getResponse(prompt, **kwargs):
                if isinstance(event, dict):
                    if event.get("type") == "token":
                        response_text += event.get("value", "")
                        yield event
                    elif event.get("type") == "final":
                        response = event.get("result", {}).get("text", response_text)
                        yield event
            # After streaming, process tool call logic
        else:
            response = self.getResponse(prompt, **kwargs)

        if response:
            self.logger.log("DEBUG", "LLM response received", response=response)
            tool_call = self.tool_manager.extract_tool_call(response)
            if tool_call == "":
                self.memory.add(response, metadata={"source": "assistant"})
                actions.append({"type": "llm", "text": response})
                # No more tool calls: summarize if requested
                if summarize:
                    summarize_kwargs = dict(kwargs)
                    stream_val = summarize_kwargs.pop('stream', stream)
                    if stream_val:
                        yield from self._summarize_actions(text, actions, stream=True, **summarize_kwargs)
                        return
                    else:
                        return self._summarize_actions(text, actions, stream=False, **summarize_kwargs)
                else:
                    return response
            else:
                self.memory.add(tool_call, metadata={"source": "tool"})
                actions.append({"type": "tool", "call": tool_call})
                # Recursively handle next step
                next_kwargs = dict(kwargs)
                next_stream = next_kwargs.pop('stream', stream)
                if next_stream:
                    yield from self.generate(text, actions=actions, max_steps=max_steps-1, summarize=summarize, stream=True, **next_kwargs)
                    return
                else:
                    return self.generate(text, actions=actions, max_steps=max_steps-1, summarize=summarize, stream=False, **next_kwargs)
        # Defensive fallback
        if summarize:
            summarize_kwargs = dict(kwargs)
            stream_val = summarize_kwargs.pop('stream', stream)
            if stream_val:
                yield from self._summarize_actions(text, actions, stream=True, **summarize_kwargs)
            else:
                return self._summarize_actions(text, actions, stream=False, **summarize_kwargs)
        else:
            return response

    def _summarize_actions(self, text, actions, stream=False, **kwargs):
        """
        Use the LLM to summarize the actions taken for the user request.
        """
        summary_prompt = (
            "Summarize the following actions taken to fulfill the user request. "
            "List all tool calls and LLM responses in order, and provide a concise summary at the end.\n\n"
            f"User request: {text}\n\n"
            f"Actions taken:\n"
            + "\n".join(
                f"- TOOL: {a['call']}" if a.get("type") == "tool" else f"- LLM: {a.get('text','')}" for a in actions
            )
        )
        self.logger.log("DEBUG", "Summarizing actions", prompt=summary_prompt)
        if stream:
            yield from self.getResponse(summary_prompt, stream=True, **kwargs)
        else:
            return self.getResponse(summary_prompt, stream=False, **kwargs)
