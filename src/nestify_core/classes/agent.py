

import importlib.util
import os
import json

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

    def build_prompt_with_memory(self, text: str, memory, tool_manager) -> str:
        """
        Build the LLM prompt using current memory, tools, and the latest user message.
        Mirrors Core.build_prompt_with_memory but scoped to Agent.
        """
        context_items = memory.search(text, top_k=3)
        context_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in context_items
        )
        tool_lines = [f"{tool['name']}: {tool['description']}" for tool in tool_manager.list_tools()]
        tools_text = "\n".join(tool_lines)
        latest_mem = memory.latest(5)
        latest_mem_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in latest_mem
        )
        prompt = ""
        if context_text:
            prompt = (
                "You are continuing a conversation. Use the relevant notes below "
                "to answer the latest user message.\n"
                f"Relevant notes:\n{context_text}\n\n"
            )
        if latest_mem_text:
            prompt += f"[Troubleshooting] Latest memory records:\n{latest_mem_text}\n\n"
        if tools_text:
            prompt += f"Available tools:\n{tools_text}\n\n"
        prompt += f"Latest user message: {text}"
        return prompt

    def generate(self, text: str, llm, memory, tool_manager, logger, **kwargs):
        """
        Generate a response from the LLM, optionally including memory context.
        All dependencies are passed in as arguments to keep Agent stateless.
        Supports streaming or non-streaming outputs.
        """
        context_items = memory.search(text, top_k=3)
        context_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in context_items
        )
        memory.add(text, metadata={"source": "user"})
        logger.log("DEBUG", "Memory context retrieved", context_count=len(context_items))
        tool_lines = [f"{tool['name']}: {tool['description']}" for tool in tool_manager.list_tools()]
        tools_text = "\n".join(tool_lines)

        # Add latest memory records for troubleshooting
        latest_mem = memory.latest(5)
        latest_mem_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in latest_mem
        )

        prompt = self.build_prompt_with_memory(text, memory, tool_manager)
        logger.log("DEBUG", "Final prompt constructed", prompt=prompt)

        stream = kwargs.get("stream", False)
        return_value = None
        if stream:
            # Streaming: accumulate tokens and yield as they arrive, then store full response at end
            response_text = ""
            for event in llm.generate(prompt, **kwargs):
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
            result = llm.generate(prompt, **kwargs)
            return_value = result.get("output") or result.get("text")
        
        # Wait for full response before adding to memory
        if return_value:
            logger.log("DEBUG", "LLM response received", response=return_value)
            # Try to extract tool calls from the response
            tool_call = tool_manager.extract_tool_call(return_value)
            if tool_call:
                logger.log("INFO", "Tool call extracted", tool_call=tool_call)
                try:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", {})
                    tool_result = tool_manager.invoke(tool_name, **tool_args)
                    logger.log("INFO", "Tool executed", tool=tool_name, args=tool_args, result=tool_result)
                    tool_result_str = f"[tool:{tool_name}] {json.dumps(tool_result)}"
                    memory.add(tool_result_str, metadata={"source": "tool"})
                    followup_prompt = self.build_prompt_with_memory(text, memory, tool_manager)
                    followup_result = llm.generate(followup_prompt, **kwargs)
                    #followup_response = followup_result.get("output") or followup_result.get("text")
                    
                    if hasattr(followup_result, '__iter__') and not isinstance(followup_result, dict):
                        # If it's a generator, exhaust it to get the final result
                        for event in followup_result:
                            if isinstance(event, dict) and event.get("type") == "final":
                                followup_response = event.get("result", {}).get("text", "")
                                break
                        else:
                            followup_response = ""
                    else:
                        followup_response = followup_result.get("output") or followup_result.get("text")

                    logger.log("DEBUG", "LLM followup response", response=followup_response)
                    memory.add(followup_response, metadata={"source": "assistant"})
                    return followup_response
                except Exception as e:
                    logger.log("ERROR", "Tool execution failed", tool=tool_name, error=str(e))
            memory.add(return_value, metadata={"source": "assistant"})
        return return_value
