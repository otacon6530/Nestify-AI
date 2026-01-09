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
    def __init__(self):
        self.correlation_id = str(uuid.uuid4())
        self.config = Config()
        self.logger = Logger()
        self.llm = LLM(self.config)
        self.memory = Memory()
        self.tool_manager = ToolManager()
        self.skills_manager = SkillsManager(self.tool_manager)
        self.mcp = MCP()
        self.agent = Agent()

    def startup(self) -> int | None:
        # Probe LLM connectivity and fail fast
        probe_result = self.llm.probe()
        if not probe_result.ok:
            self.logger.log("ERROR", "LLM probe failed", reason=probe_result.reason, correlation_id=self.correlation_id)
            env = build_error_envelope(
                code="NETWORK_ERROR" if "Network error" in (probe_result.reason or "") else "PROVIDER_ERROR",
                message=f"LLM startup probe failed: {probe_result.reason}",
                component="Core/LLM",
                correlation_id=self.correlation_id,
                suggestion="Check network, base_url, and API credentials",
            )
            return emit_error(env)
        self.logger.log("INFO", "LLM probe succeeded", correlation_id=self.correlation_id)
        return None

    def exec_once(self, text: str) -> int:
        try:
            result = self.llm.generate(text)
            self.logger.log("INFO", "exec result", correlation_id=self.correlation_id)
            sys.stdout.write(result.get("output", "") + "\n")
            sys.stdout.flush()
            return 0
        except Exception as e:
            self.logger.log("ERROR", "exec failed", correlation_id=self.correlation_id)
            env = build_error_envelope(
                code="UNKNOWN",
                message=str(e),
                component="Core/Exec",
                correlation_id=self.correlation_id,
                exc=e,
            )
            return emit_error(env)
