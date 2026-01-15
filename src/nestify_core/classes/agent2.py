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

    def getResponse(self, prompt: str, **kwargs):
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
    
    def plan(self, text, actions):
        plan = []
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
            f"Available tools:\n{str(self.tool_manager.list_tools())}\n"
            f"Actions Taken:\n{chr(10).join(json.dumps(a) for a in actions)}\n"
            f"User message:\n{text}\n"
        )
        return self.extract_plan(self.getResponse(planning_prompt, stream=False))
    
    def tools(self, actions, step):
        tool_name = step.get("name")
        tool_args = step.get("args", {})
        if tool_name in self.tool_manager.tools:
            tool_result = self.tool_manager.invoke(tool_name, **tool_args)
            actions.append({"type": "tool", "name": tool_name, "args": tool_args, "result": tool_result})
        else:
            actions.append({"type": "error", "message": f"Unknown tool {tool_name}"})
    
    def think(self, actions, text):
        think_prompt = (
            "You are Nestify Agent.\n"
            "Use the notes below to perform the current plan step.\n\n"
            f"Latest user message: {text}"
        )
        return self.getResponse(think_prompt, stream=False)
    
    def done_check(self, plan, actions, text):
        done_when = plan.get("done_when", "").lower()
        if not done_when:
            return False
        # Ask the LLM if the request is satisfied
        review_prompt = (
            "Based on the following actions and the original user request, is the request fully satisfied?\n"
            "Reply with 'true' if done, 'false' if more steps are needed.\n\n"
            f"User request: {text}\n"
            f"Plan done_when: {done_when}\n"
            f"Actions taken:\n{chr(10).join(json.dumps(a) for a in actions)}\n"
        )
        resp = self.getResponse(review_prompt, stream=False)
        return "true" in resp.lower()
    
    def execute(self, text):
        actions = []
        max_exec_steps = 200
        done = False
        
        while max_exec_steps > 0 and not done:
            max_exec_steps -= 1
            plan = self.plan(text, actions)
            if plan and 'steps' in plan:
                step = plan['steps'][0]
                s_type = step.get("type")
                if s_type == "tool":
                    self.tools(actions, step)   
                elif s_type == "think":
                    self.think(actions, text)
            done = self.done_check(plan, actions, text)
        return actions

    def generate(self, text: str, **kwargs):
        actions = self.execute(text)
        prompt = (
            "Summarize the actions base on the request.\n\n"
            "Keep in mind that no actions were communicated back to the user yet and will need to be in your response.\n\n"
            f"User request: {text}\n"
            f"Actions taken:\n{chr(10).join(json.dumps(a) for a in actions)}\n"
        )
        response_text = self.getResponse(prompt, stream=False)
        
        #Stream the response if requested
        stream = kwargs.get("stream", False)
        if stream:      
            # Simulate streaming by yielding tokens one by one
            for token in response_text.split():
                yield {"type": "token", "value": token + " "}
            yield {"type": "final", "result": {"text": response_text}}
        else:
            # Return a dict with expected keys for compatibility
            return {"output": response_text, "text": response_text, "actions": [{"type": "llm", "text": response_text}]}