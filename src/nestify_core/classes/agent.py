

import importlib.util
import os
import json
import re

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

    def extract_plan(self, text: str):
        """
        Extract a structured plan from a fenced ```plan block or a top-level JSON object.
        Returns a dict if found and parsed successfully, else None.
        """
        if not isinstance(text, str):
            return None
        try:
            fence = "```plan"
            start_fence = text.find(fence)
            if start_fence != -1:
                start_json = text.find("{", start_fence)
                end_fence = text.find("```", start_json + 1)
                if start_json != -1 and end_fence != -1:
                    raw = text[start_json:end_fence]
                    return json.loads(raw)
            first = text.find("{")
            last = text.rfind("}")
            if first != -1 and last != -1 and last > first:
                return json.loads(text[first:last + 1])
        except Exception:
            return None
        return None

    def format_plan(self, plan_obj):
        """Normalize parsed plan JSON into a list of step dicts with default status."""
        formatted = []
        if isinstance(plan_obj, dict):
            steps = plan_obj.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        if "status" not in step:
                            step["status"] = "pending"
                        formatted.append(step)
        elif isinstance(plan_obj, list):
            for step in plan_obj:
                if isinstance(step, dict):
                    if "status" not in step:
                        step["status"] = "pending"
                    formatted.append(step)
        return formatted

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

    def getResponse2(self, prompt: str, **kwargs):
        """
        Non-yielding helper that always returns a plain string.
        If stream=True, consumes the stream internally and optionally forwards
        events via an on_event callback.
        """
        stream = bool(kwargs.pop("stream", False))
        on_event = kwargs.pop("on_event", None)

        if stream:
            response_text = ""
            for event in self.llm.generate(prompt, stream=True, **kwargs):
                if isinstance(event, dict):
                    if event.get("type") == "token":
                        response_text += event.get("value", "")
                        if callable(on_event):
                            try:
                                on_event(event)
                            except Exception:
                                pass
                    elif event.get("type") == "final":
                        final_text = event.get("result", {}).get("text", response_text)
                        if callable(on_event):
                            try:
                                on_event(event)
                            except Exception:
                                pass
                        return final_text or response_text
            return response_text
        else:
            result = self.llm.generate(prompt, **kwargs)
            if isinstance(result, dict):
                return (result.get("output") or result.get("text") or "")
            # Fallback: stringify unexpected provider return types
            return str(result or "")
    def _actions_to_prompt(self, actions):
        lines = []
        for a in actions or []:
            t = a.get("type")
            if t == "plan":
                lines.append(f"- PLAN: {a.get('text','').strip()[:500]}")
            elif t == "tool":
                lines.append(f"- TOOL {a.get('tool','')}: {json.dumps(a.get('call'), ensure_ascii=False)[:500]}")
            elif t == "tool_error":
                lines.append(f"- TOOL_ERROR {a.get('tool','')}: {a.get('error','')}")
            elif t == "tool_denied":
                lines.append(f"- TOOL_DENIED {a.get('tool','')}: {json.dumps(a.get('call'), ensure_ascii=False)[:500]}")
            elif t == "llm":
                lines.append(f"- LLM: {str(a.get('text',''))[:500]}")
            elif t == "review":
                lines.append(f"- REVIEW: decision={a.get('decision','')} remaining_steps={a.get('remaining_steps')}")
            else:
                lines.append(f"- OTHER: {json.dumps(a, ensure_ascii=False)[:500]}")
        if not lines:
            return ""
        return "\n".join(lines)

    def _has_pending_steps(self, plan) -> bool:
        """True if any plan step is not marked done. Blocked steps are not considered resolved."""
        for s in plan or []:
            if not isinstance(s, dict):
                return True
            status = s.get("status")
            if status != "done":
                return True
        return False
    def generate(self, text: str, actions=None, max_steps=100, summarize=True, **kwargs):
        """Run multi-step reasoning with optional tool approvals and final summary."""
        loop = False
        response = ""

        if actions is None:
            actions = []
        plan = []
        while loop == False and max_steps > 0:
            max_steps -= 1
            context_text = self.getMemory(text)
            self.memory.add(text, metadata={"source": "user"})
            context_text += self.getTools(text)
            
            planning_prompt = (
                "You are Nestify Agent.\n"
                "Plan your approach BEFORE answering.\n"
                "Return ONLY a single fenced plan block in the exact format below. No prose.\n\n"
                "Fence and JSON schema:\n"
                "```plan\n"
                "{\n"
                '  "goal": "<short optional goal>",\n'
                '  "steps": [\n'
                '    {"type": "tool", "name": "<tool_name>", "args": { /* JSON args */ }},\n'
                '    {"type": "think", "instruction": "<concise internal analysis step>"}\n'
                "  ],\n"
                '  "done_when": "<optional completion condition>"\n'
                "}\n"
                "```\n"
                "Rules:\n"
                "- Use only the available tools shown below when planning tool steps.\n"
                "- Each step is a valid JSON object. No comments and no trailing commas.\n"
                "- Do NOT output anything before or after the fenced plan block.\n"
                "- If no tools are needed (e.g., greetings), return a minimal plan with one think step.\n\n"
                "- Include a measurable done_when condition (e.g., 'all files read', 'API response validated').\n"
                "- Do not end with a summary unless explicitly requested; finish by completing the steps.\n\n"
                "Example:\n"
                "```plan\n"
                "{\n"
                '  "goal": "Review classes under src/nestify_core/classes",\n'
                '  "steps": [\n'
                '    {"type":"tool","name":"list_dir","args":{"path":"src/nestify_core/classes"}},\n'
                '    {"type":"tool","name":"read_file","args":{"path":"src/nestify_core/classes/agent.py"}},\n'
                '    {"type":"think","instruction":"Summarize agent.py briefly"}\n'
                "  ],\n"
                '  "done_when": "Summaries produced for each class file"\n'
                "}\n"
                "```\n\n"
                f"User message:\n{text}\n\n"
                "Available tools and notes:\n"
                f"{context_text}\n"
            )
            plan_resp = self.getResponse2(planning_prompt, stream=False)
            plan_data = self.extract_plan(plan_resp) if plan_resp else None
            if plan_data:
                plan = self.format_plan(plan_data)
            # Record the planning output for this iteration
            if plan_resp:
                # Log the raw generated plan and the normalized steps
                self.logger.log("INFO", "Plan generated", plan_text=plan_resp, plan_steps=plan)
                actions.append({"type": "plan", "text": plan_resp, "steps": plan})

            for idx, step in enumerate(plan):
                #if not isinstance(step, dict):
                #    continue
                #if step.get("status") not in (None, "pending"):
                #    continue

                s_type = step.get("type")
                if s_type == "tool":
                    tool_name = step.get("name")
                    tool_args = dict(step.get("args", {}))
                    try:
                        result = self.tool_manager.invoke(tool_name, **tool_args)
                        actions.append({"type": "tool", "tool": tool_name, "call": result})
                        self.memory.add(result, metadata={"source": "tool"})
                        step["status"] = "done"
                        # Log executed tool step
                        self.logger.log(
                            "INFO", "Step executed",
                            step_type="tool",
                            step_index=idx,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            result=result,
                            status="done"
                        )
                    except Exception as exc:
                        actions.append({"type": "tool_error", "tool": tool_name, "error": str(exc)})
                        step["status"] = "blocked"
                        # Log tool error step
                        self.logger.log(
                            "ERROR", "Step execution failed",
                            step_type="tool",
                            step_index=idx,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            error=str(exc),
                            status="blocked"
                        )
                    continue
                elif s_type == "think":
                    instruction = step.get("instruction", "Continue analysis.")
                    think_prompt = (
                        "Use the notes below to perform the current plan step.\n\n"
                        f"{context_text}\n\n"
                        f"Plan step: {json.dumps(step, ensure_ascii=False)}\n"
                        f"Latest user message: {text}"
                    )
                    try:
                        resp = self.getResponse2(think_prompt, stream=False)
                        actions.append({"type": "llm", "text": resp})
                        self.memory.add(resp, metadata={"source": "assistant"})
                        step["status"] = "done"
                        # Log executed think step
                        self.logger.log(
                            "INFO", "Step executed",
                            step_type="think",
                            step_index=idx,
                            instruction=instruction,
                            result=resp,
                            status="done"
                        )
                        contexpt_text = self.getMemory(text)
                        self.memory.add(text, metadata={"source": "user"})
                        context_text += self.getTools(text)
                    except Exception as exc:
                        actions.append({"type": "think_error", "error": str(exc)})
                        step["status"] = "blocked"
                        self.logger.log(
                            "ERROR", "Think step execution failed",
                            step_type="think",
                            step_index=idx,
                            instruction=instruction,
                            error=str(exc),
                            status="blocked"
                        )
                    continue
                else:
                    # Unknown step type
                    self.logger.log(
                        "WARNING", "Unknown step type",
                        step_type=s_type,
                        step_index=idx,
                        step=step
                    )
                    continue
            context_text = self.getMemory(text)
            context_text += self.getTools(text) 
            # Prefer deterministic completion: if a plan exists and all steps are resolved,
            # consider the task complete; otherwise continue.
            if plan:
                done = not self._has_pending_steps(plan)
                actions.append({"type": "review", "decision": str(done).lower(), "remaining_steps": max_steps})
                loop = bool(done)
            else:
                # Fallback to LLM-based completion assessment when no plan was extracted
                prompt = (
                    "Decide whether the latest user request/comment is already satisfied using the notes, or needs no further steps.\n"
                    "If yes, reply 'true'; otherwise reply 'false'.\n"
                    "Output exactly one lowercase word on a single line. Do not include any other text."
                    "Notes:\n"
                    f"{context_text}\n\n"
                    f"Latest user message: {text}\n"
                )
                self.logger.log("DEBUG", "Checking if task is complete", prompt=prompt) 
                self.logger.log("DEBUG", "Max steps", max_steps=max_steps)  
                response = self.getResponse2(prompt, stream=False)
                self.logger.log("DEBUG", "Completion check response", response=response)
                actions.append({"type": "review", "decision": response, "remaining_steps": max_steps})
                if "true" in response:
                    loop = True

        context_text = self.getMemory(text)
        context_text += self.getTools(text)

        prompt = (
            "You are continuing a conversation. Use the relevant notes below "
            "to answer the latest user message.\n\n"
            f"{context_text}\n\n"
            f"Latest user message: {text}"
        )
        
        stream = kwargs.pop("stream", False)
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
            final_text = self.getResponse(prompt, **kwargs)
            actions.append({"type": "llm", "text": final_text})
            return {"text": final_text, "actions": actions}
        
    def generate2(self, text: str, actions=None, max_steps=8, summarize=True, **kwargs):
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
