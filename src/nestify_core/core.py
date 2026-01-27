
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
from .classes.config import Config
from .classes.logger import Logger
from .classes.llm import LLM
from .classes.memory import Memory
from .classes.tool_manager import ToolManager
from .classes.skills_manager import SkillsManager
from .classes.mcp import MCP
from .classes.agent3 import Agent
from .functions.error_envelope import build_error_envelope, emit_error

class Core:
    """
    Core orchestrates the main components of the Nestify system:
    - Loads configuration and logger
    - Initializes LLM, memory, tool/skills managers, agent, and MCP
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
        self.agent = Agent(self.memory, self.tool_manager, self.llm, self.logger)


    
    def generate(self, text: str, **kwargs):
        """
        Delegate generation to the Agent's implementation.
        This keeps Core thin and the Agent responsible for orchestration.
        """
        return self.agent.generate(text, **kwargs)
    
    
        
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