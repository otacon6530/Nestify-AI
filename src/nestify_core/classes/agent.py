

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
        # Track per-tool session approvals (e.g., approve-all choices)
        self.session_tool_approvals = {}

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
        """Run multi-step reasoning with optional tool approvals and final summary."""
        if actions is None:
            actions = []

        stream = kwargs.pop("stream", False)
        approval_callback = kwargs.pop("approval_callback", None)

        if max_steps <= 0:
            actions.append({"type": "error", "message": "Max steps exceeded."})
            summarize_kwargs = dict(kwargs)
            stream_val = summarize_kwargs.pop("stream", stream)
            if stream_val:
                yield from self._summarize_actions(text, actions, stream=True, **summarize_kwargs)
                return
            return self._summarize_actions(text, actions, stream=False, **summarize_kwargs)

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

        response = None
        if stream:
            response_text = ""
            for event in self.getResponse(prompt, stream=True, **kwargs):
                if isinstance(event, dict):
                    if event.get("type") == "token":
                        response_text += event.get("value", "")
                        yield event
                    elif event.get("type") == "final":
                        response = event.get("result", {}).get("text", response_text)
                        yield event
        else:
            response = self.getResponse(prompt, **kwargs)

        if response:
            self.logger.log("DEBUG", "LLM response received", response=response)
            tool_invocation = self.tool_manager.extract_tool_call(response)
            if not tool_invocation:
                self.memory.add(response, metadata={"source": "assistant"})
                actions.append({"type": "llm", "text": response})
                summarize_kwargs = dict(kwargs)
                stream_val = summarize_kwargs.pop("stream", stream)
                if summarize:
                    if stream_val:
                        yield from self._summarize_actions(text, actions, stream=True, **summarize_kwargs)
                        return
                    return self._summarize_actions(text, actions, stream=False, **summarize_kwargs)
                return response

            tool_name = tool_invocation.get("name")
            tool_args = dict(tool_invocation.get("args", {}))

            auto_approve = bool(self.session_tool_approvals.get(tool_name))
            result_record = None
            denial_record = None
            error_record = None
            current_args = dict(tool_args)

            try:
                if auto_approve:
                    approved_args = dict(tool_args)
                    approved_args["approve"] = "all"
                    current_args = approved_args
                    result_record = self.tool_manager.invoke(tool_name, **approved_args)
                elif self.tool_manager.needs_approval(tool_name):
                    sanitized_args = dict(tool_args)
                    sanitized_args.pop("approve", None)
                    current_args = sanitized_args
                    preliminary = self.tool_manager.invoke(tool_name, **sanitized_args)

                    if isinstance(preliminary, dict) and preliminary.get("status") == "needs_approval":
                        approval = {"approved": False, "approve_all": False}
                        if callable(approval_callback):
                            callback_response = approval_callback(
                                tool_name=tool_name,
                                tool_args=sanitized_args,
                                pending=preliminary,
                            )
                            if callback_response is not None:
                                approval = callback_response

                        if not approval.get("approved"):
                            self.session_tool_approvals.pop(tool_name, None)
                            denial_record = {
                                "status": "denied",
                                "tool": tool_name,
                                "command": preliminary.get("command") or sanitized_args.get("command"),
                                "message": "User denied execution",
                            }
                        else:
                            if approval.get("approve_all"):
                                self.session_tool_approvals[tool_name] = True
                            approved_args = dict(sanitized_args)
                            approved_args["approve"] = "all" if approval.get("approve_all") else "yes"
                            current_args = approved_args
                            result_record = self.tool_manager.invoke(tool_name, **approved_args)
                    else:
                        result_record = preliminary
                else:
                    current_args = tool_args
                    result_record = self.tool_manager.invoke(tool_name, **tool_args)
            except Exception as exc:
                error_record = {
                    "status": "error",
                    "tool": tool_name,
                    "details": str(exc),
                    "args": current_args,
                }

            if denial_record is not None:
                actions.append({"type": "tool_denied", "tool": tool_name, "call": denial_record})
                self.memory.add(denial_record, metadata={"source": "tool"})
                next_kwargs = dict(kwargs)
                next_kwargs["stream"] = stream
                if approval_callback:
                    next_kwargs["approval_callback"] = approval_callback
                if stream:
                    yield from self.generate(
                        text,
                        actions=actions,
                        max_steps=max_steps - 1,
                        summarize=summarize,
                        **next_kwargs,
                    )
                    return
                return self.generate(
                    text,
                    actions=actions,
                    max_steps=max_steps - 1,
                    summarize=summarize,
                    **next_kwargs,
                )

            if error_record is not None:
                actions.append({"type": "tool_error", "tool": tool_name, "call": error_record})
                self.memory.add(error_record, metadata={"source": "tool"})
            else:
                actions.append({"type": "tool", "tool": tool_name, "call": result_record})
                if result_record is not None:
                    self.memory.add(result_record, metadata={"source": "tool"})

            next_kwargs = dict(kwargs)
            next_kwargs["stream"] = stream
            if approval_callback:
                next_kwargs["approval_callback"] = approval_callback
            if stream:
                yield from self.generate(
                    text,
                    actions=actions,
                    max_steps=max_steps - 1,
                    summarize=summarize,
                    **next_kwargs,
                )
                return
            return self.generate(
                text,
                actions=actions,
                max_steps=max_steps - 1,
                summarize=summarize,
                **next_kwargs,
            )

        summarize_kwargs = dict(kwargs)
        stream_val = summarize_kwargs.pop("stream", stream)
        if summarize:
            if stream_val:
                yield from self._summarize_actions(text, actions, stream=True, **summarize_kwargs)
                return
            return self._summarize_actions(text, actions, stream=False, **summarize_kwargs)
        return response

    def _summarize_actions(self, text, actions, stream=False, **kwargs):
        """
        Use the LLM to summarize the actions taken for the user request.
        """
        action_lines = []
        for action in actions:
            a_type = action.get("type")
            if a_type == "tool":
                descriptor = action.get("tool", "tool")
                call_repr = json.dumps(action.get("call"), ensure_ascii=False)
                action_lines.append(f"- TOOL {descriptor}: {call_repr}")
            elif a_type == "tool_denied":
                descriptor = action.get("tool", "tool")
                call_repr = json.dumps(action.get("call"), ensure_ascii=False)
                action_lines.append(f"- TOOL_DENIED {descriptor}: {call_repr}")
            elif a_type == "tool_error":
                descriptor = action.get("tool", "tool")
                call_repr = json.dumps(action.get("call"), ensure_ascii=False)
                action_lines.append(f"- TOOL_ERROR {descriptor}: {call_repr}")
            elif a_type == "llm":
                action_lines.append(f"- LLM: {action.get('text', '')}")
            elif a_type == "error":
                action_lines.append(f"- ERROR: {json.dumps(action, ensure_ascii=False)}")
            else:
                action_lines.append(f"- OTHER: {json.dumps(action, ensure_ascii=False)}")

        summary_prompt = (
            "Summarize the following actions taken to fulfill the user request. "
            "List all tool calls and LLM responses in order, and provide a concise summary at the end.\n\n"
            f"User request: {text}\n\n"
            "Actions taken:\n"
            + "\n".join(action_lines)
        )
        self.logger.log("DEBUG", "Summarizing actions", prompt=summary_prompt)
        if stream:
            yield from self.getResponse(summary_prompt, stream=True, **kwargs)
        else:
            return self.getResponse(summary_prompt, stream=False, **kwargs)
