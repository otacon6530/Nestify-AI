from __future__ import annotations
from ..functions.llm_generate import generate_echo
from ..functions.llm_probe import probe, ProbeResult
from ..functions.provider_openai import generate_openai, probe_openai


class LLM:
    def __init__(self, config):
        self.provider = config.get("llm", "provider", default="echo")
        self.model = config.get("llm", "model", default="local-echo")
        self.base_url = config.get("llm", "base_url", default=None)
        self.api_key = config.get("llm", "api_key", default=None)
        self.timeout_seconds = config.get("probe", "timeout_seconds", default=5)
        # Bind methods
        self.generate = lambda prompt, **kwargs: self._generate_impl(prompt, **kwargs)
        self.probe = self._probe_impl

    def _probe_impl(self) -> ProbeResult:
        if self.provider == "openai":
            return probe_openai(self.base_url, self.api_key, self.timeout_seconds)
        return probe(self.provider, self.base_url, self.timeout_seconds)

    def _generate_impl(self, prompt: str, **kwargs):
        if self.provider == "echo":
            return generate_echo(prompt, self.model, **kwargs)
        if self.provider == "openai":
            return generate_openai(prompt, self.model, self.base_url, self.api_key, **kwargs)
        return {"provider": self.provider, "model": self.model, "output": f"(stub) {prompt}"}
