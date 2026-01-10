
"""
core.py - Nestify Core Orchestration

This module defines the Core class, which orchestrates configuration, logging, LLM connectivity, memory, tool and skills management, and agent lifecycle for the Nestify system.

Key responsibilities:
- Load and manage configuration
- Initialize and probe LLM provider
- Set up logging, memory, tools, skills, and agent
- Provide startup and exec_once entry points for CLI and bridge

Copyright (c) Nestify contributors. MIT License.
"""


from __future__ import annotations
import sys
import uuid
from .classes.config import Config
from .classes.logger import Logger
from .classes.llm import LLM
from .classes.memory import Memory
from .classes.tool_manager import ToolManager
from .classes.skills_manager import SkillsManager
from .classes.mcp import MCP
from .classes.agent import Agent
from .functions.error_envelope import build_error_envelope, emit_error

class Core:
    """
    Core orchestrates the main components of the Nestify system:
    - Loads configuration and logger
    - Initializes LLM, memory, tool/skills managers, agent, and MCP
    - Provides startup() for LLM connectivity probe
    - Provides exec_once() for single-shot text execution
    """
    def __init__(self):
        """
        Initialize all core components: config, logger, LLM, memory, tools, skills, MCP, and agent.
        """
        # Removed correlation_id; not used for tracing in current implementation
        self.config = Config()
        self.logger = Logger()
        self.llm = LLM(self.config, self.logger)
        self.memory = Memory(self.llm.embed)
        self.tool_manager = ToolManager()
        self.skills_manager = SkillsManager(self.tool_manager)
        self.mcp = MCP()
        self.agent = Agent()

    def startup(self) -> int | None:
        """
        Old code that should be removed in future versions.
        """
        return
    
    def generate(self, text: str, **kwargs):
        """
        Generate a response from the LLM, optionally including memory context.
        Args:
            text: User query or prompt.
            kwargs: Additional arguments for LLM (e.g., stream=True).
        Returns:
            LLM response (stream or dict).
        """
        context_items = self.memory.search(text, top_k=3)
        context_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in context_items
        )
        self.memory.add(text, metadata={"source": "user"})
        self.logger.log("DEBUG", "Memory context retrieved", context_count=len(context_items))
        tool_lines = [f"{tool['name']}: {tool['description']}" for tool in self.tool_manager.list_tools()]
        tools_text = "\n".join(tool_lines)

        # Add latest memory records for troubleshooting
        latest_mem = self.memory.latest(5)
        latest_mem_text = "\n---\n".join(
            f"[{item.get('metadata', {}).get('source', 'unknown')}] {item['text']}" for item in latest_mem
        )

        prompt = ""
        if context_text:
            prompt = (
                "You are continuing a conversation. Use the relevant notes below "
                "to answer the latest user message.\n"  # brief instruction for clarity
                f"Relevant notes:\n{context_text}\n\n"
            )

        if latest_mem_text:
            prompt += f"[Troubleshooting] Latest memory records:\n{latest_mem_text}\n\n"

        if tools_text:
            prompt += f"Available tools:\n{tools_text}\n\n"

        prompt += f"Latest user message: {text}"

        self.logger.log("DEBUG", "Final prompt constructed", prompt=prompt)

        stream = kwargs.get("stream", False)
        if stream:
            # Streaming: accumulate tokens and yield as they arrive, then store full response at end
            def stream_wrapper():
                response_text = ""
                for event in self.llm.generate(prompt, **kwargs):
                    if isinstance(event, dict):
                        if event.get("type") == "token":
                            response_text += event.get("value", "")
                            yield event
                        elif event.get("type") == "final":
                            # Prefer full text from final event if present
                            response_text = event.get("result", {}).get("text", response_text)
                            yield event
                # Store the assistant's full reply in memory after stream ends
                if response_text:
                    self.memory.add(response_text, metadata={"source": "assistant"})
            return stream_wrapper()
        else:
            # Non-streaming: store output immediately
            result = self.llm.generate(prompt, **kwargs)
            output = result.get("output") or result.get("text")
            if output:
                self.memory.add(output, metadata={"source": "assistant"})
            return result
        
    def exec_once(self, text: str) -> int:
        """
        Run a single LLM generation and print the result to stdout.
        Returns 0 on success, or error exit code on failure.
        """
        try:
            result = self.generate(text)
            self.logger.log("INFO", "exec result")
            sys.stdout.write(result.get("output", "") + "\n")
            sys.stdout.flush()
            return 0
        except Exception as e:
            self.logger.log("ERROR", "exec failed")
            env = build_error_envelope(
                code="UNKNOWN",
                message=str(e),
                component="Core/Exec",
                exc=e,
            )
            return emit_error(env)
