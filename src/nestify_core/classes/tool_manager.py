import importlib
import pkgutil
import sys
import os
import json
import re

class ToolManager:
    def __init__(self):
        self.tools = {}  # name -> function
        self.tool_info = {}  # name -> {"description": str}
        self.requires_approval = set()
        self._auto_register_tools()

    def _auto_register_tools(self):
        """Auto-import and register all tools in the tools folder that define TOOL_NAME and TOOL_DESCRIPTION."""
        import nestify_core.tools
        tools_pkg = nestify_core.tools
        pkg_path = tools_pkg.__path__
        for _, modname, ispkg in pkgutil.iter_modules(pkg_path):
            if ispkg:
                continue
            module = importlib.import_module(f"nestify_core.tools.{modname}")
            # Look for a function with TOOL_NAME and TOOL_DESCRIPTION
            tool_name = getattr(module, "TOOL_NAME", None)
            tool_desc = getattr(module, "TOOL_DESCRIPTION", "")
            # Convention: function named <tool_name>_tool
            func = getattr(module, f"{tool_name}_tool", None) if tool_name else None
            if tool_name and func:
                self.register(tool_name, func, description=tool_desc)

    def register(self, name: str, func, description: str = "", requires_approval: bool = False):
        self.tools[name] = func
        self.tool_info[name] = {"description": description}
        if requires_approval:
            self.requires_approval.add(name)

    def invoke(self, name: str, *args, **kwargs):
        if name not in self.tools:
            raise KeyError(f"Unknown tool {name}")
        return self.tools[name](*args, **kwargs)

    def list_tools(self):
        """Return a list of tool metadata: name and description."""
        return [
            {"name": name, "description": info["description"]}
            for name, info in self.tool_info.items()
        ]

        def extract_tool_call(response_text):
            # Look for a code block with ```tool
            match = re.search(r"```tool\\s*(\\{.*?\\})\\s*```", response_text, re.DOTALL)
            if match:
                try:
                    tool_call = json.loads(match.group(1))
                    return tool_call
                except Exception:
                    return None
            # Fallback: try to parse any JSON in the response
            try:
                tool_call = json.loads(response_text)
                if "tool_call" in tool_call or ("name" in tool_call and "args" in tool_call):
                    return tool_call
            except Exception:
                pass
            return None
