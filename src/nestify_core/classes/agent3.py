import json

class Agent:
    def __init__(self, memory, tool_manager, llm, logger, max_exec_steps=20):
        self.memory = memory
        self.tool_manager = tool_manager
        self.llm = llm
        self.logger = logger
        self.max_exec_steps = max_exec_steps

    def get_condensed_memory(self):
        """
        Pull latest memory and condense to minimal JSON string.
        """
        mem = self.memory.get_latest()
        if isinstance(mem, str):
            try:
                mem = json.loads(mem)
            except Exception:
                mem = {}
        # Only keep recent, relevant, and high-value context
        condensed = {
            "recent": mem.get("recent", []),
            "important": mem.get("important", []),
        }
        return json.dumps(condensed)

    def get_tools_json(self):
        """
        Return available tools and descriptions as condensed JSON string.
        """
        tools = self.tool_manager.list_tools()
        if isinstance(tools, str):
            try:
                tools = json.loads(tools)
            except Exception:
                tools = {}
        # Only name and short description
        condensed = {name: tool.get("description", "") for name, tool in tools.items()}
        return json.dumps(condensed)

    def clarify_request(self, user_request):
        """
        Use LLM to clarify and reword the user request with specific details.
        """
        clarify_prompt = (
            f"Clarify and reword the following request for execution. "
            f"Gather any needed information first.\nRequest: {user_request}"
        )
        clarified = self.llm.generate(clarify_prompt, stream=False)
        # Assume output is a dict with 'clarified_request' key
        if isinstance(clarified, dict) and "clarified_request" in clarified:
            return clarified["clarified_request"]
        return clarified if isinstance(clarified, str) else str(clarified)

    def generate_plan(self, clarified_request):
        """
        Use LLM to output a plan of tool calls and think steps.
        """
        plan_prompt = (
            f"Given the clarified request, output a plan as a JSON array of steps.\n"
            "Each step must be an object with: type ('tool' or 'think'), name (for tools), args (for tools), instruction (for think).\n"
            "No extra text, only the JSON array.\n"
            "Schema example:\n"
            "[\n"
            "  {\"type\": \"tool\", \"name\": \"list_dir\", \"args\": {\"path\": \"src/classes\"}},\n"
            "  {\"type\": \"think\", \"instruction\": \"Summarize the files found in the directory.\"}\n"
            "]\n"
            f"Request: {clarified_request}"
        )
        plan = self.llm.generate(plan_prompt, stream=False)
        return plan

    def execute_plan(self, plan):
        """
        Execute the plan. Abort if any tool call fails.
        """
        actions = []
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except Exception:
                plan = []
        for step in plan:
            if not isinstance(step, dict):
                continue
            s_type = step.get("type")
            self.logger.log("DEBUG", f"Executing step: {json.dumps(step)}")
            if s_type == "tool":
                tool_name = step.get("name")
                tool_args = step.get("args", {})
                if tool_name in self.tool_manager.tools:
                    try:
                        result = self.tool_manager.invoke(tool_name, **tool_args)
                        action = {"type": "tool", "name": tool_name, "result": result}
                        actions.append(action)
                        self.logger.log("INFO", f"Tool {tool_name} succeeded.", action=action)
                    except Exception as exc:
                        action = {"type": "error", "name": tool_name, "error": str(exc)}
                        actions.append(action)
                        self.logger.error(f"Tool {tool_name} failed: {exc}", action=action)
                        break
                else:
                    action = {"type": "error", "name": tool_name, "error": "Unknown tool"}
                    actions.append(action)
                    self.logger.error(f"Unknown tool: {tool_name}", action=action)
                    break
            elif s_type == "think":
                instruction = step.get("instruction", "")
                think_prompt = f"Instruction: {instruction}\nActions so far: {json.dumps(actions)}"
                response = self.llm.generate(think_prompt, stream=False)
                action = {"type": "think", "instruction": instruction, "response": response}
                actions.append(action)
                self.logger.log("INFO", f"Think step executed: {instruction}", action=action)
        self.logger.log("INFO", "All actions executed", actions=actions)
        return actions

    def is_done(self, actions, original_request):
        """
        Use LLM to determine if more actions are needed.
        """
        done_prompt = (
            "Based on the actions and the original request, is the request fully satisfied? "
            "Reply with 'true' if done, 'false' if more steps are needed.\n"
            f"Request: {original_request}\nActions: {json.dumps(actions)}"
        )
        resp = self.llm.generate(done_prompt, stream=False)
        return "true" in str(resp).lower()

    def orchestrate(self, user_request, stream=False):
        """
        Orchestrate between simple and plan execution modes.
        """
        # Simple heuristic: if request is short/greeting/joke, use simple
        if user_request.strip().lower() in ["hello", "hi", "hey", "tell me a joke"]:
            response = self.llm.generate(user_request, stream=stream)
            if stream:
                if hasattr(response, '__iter__') and not isinstance(response, str):
                    for token in response:
                        yield token
                else:
                    for token in str(response).split():
                        yield token + " "
            else:
                return response
        else:
            clarified = self.clarify_request(user_request)
            exec_count = self.max_exec_steps
            actions = []
            while exec_count > 0:
                exec_count -= 1
                plan = self.generate_plan(clarified)
                actions = self.execute_plan(plan)
                if self.is_done(actions, user_request):
                    break
            summary_prompt = (
                "Summarize the results of the following actions for the user.\n"
                f"Request: {user_request}\nActions: {json.dumps(actions)}"
            )
            summary = self.llm.generate(summary_prompt, stream=stream)
            if stream:
                if hasattr(summary, '__iter__') and not isinstance(summary, str):
                    for token in summary:
                        yield token
                else:
                    for token in str(summary).split():
                        yield token + " "
            else:
                return summary

    def generate_sync(self, user_request):
        """
        Non-streaming version of generate.
        """
        return self.orchestrate(user_request, stream=False)

    def generate(self, user_request, stream=False, **kwargs):
        """
        Streaming version of generate.
        """
        if stream:
            return self.orchestrate(user_request, stream=True)
        else:
            return self.orchestrate(user_request, stream=False)
