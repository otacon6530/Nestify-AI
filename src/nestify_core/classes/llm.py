from __future__ import annotations
from ..functions.llm_generate import generate_echo
from ..functions.llm_probe import probe, ProbeResult


class LLM:
    def __init__(self, config):
        self.provider = config.get("llm", "provider", default="echo")
        self.model = config.get("llm", "model", default="local-echo")
        self.base_url = config.get("llm", "base_url", default=None)
        self.timeout_seconds = config.get("probe", "timeout_seconds", default=5)
        # Bind methods
        self.generate = lambda prompt, **kwargs: self._generate_impl(prompt, **kwargs)
        self.probe = lambda: probe(self.provider, self.base_url, self.timeout_seconds)

    def _generate_impl(self, prompt: str, **kwargs):
        if self.provider == "echo":
            return generate_echo(prompt, self.model, **kwargs)
        # Placeholder: extend with real providers
        return {"provider": self.provider, "model": self.model, "output": f"(stub) {prompt}"}
