from __future__ import annotations
from ..functions.llm_generate import generate_echo, generate_echo_stream
from ..functions.llm_probe import probe, ProbeResult
from ..functions.provider_openai import generate_openai, probe_openai
from ..functions.error_envelope import build_error_envelope, emit_error


class LLM:
    def __init__(self, config, logger):
        self.logger = logger
        self.provider = config.get("llm", "provider", default="echo")
        self.model = config.get("llm", "model", default="local-echo")
        self.base_url = config.get("llm", "base_url", default=None)
        self.api_key = config.get("llm", "api_key", default=None)
        self.timeout_seconds = config.get("probe", "timeout_seconds", default=5)
        # Bind methods
        self.generate = lambda prompt, **kwargs: self._generate_impl(prompt, **kwargs)
        self.probe = self._probe_impl
        self.embed = self._embed_impl
    
    def _embed_impl(self, text: str):
        """
        Return embedding vector for text/code using the configured provider/model.
        If no embedding model is configured, returns None.
        """
        # Example: OpenAI embedding API, HuggingFace, or local model
        # This is a stub; replace with actual embedding logic
        if hasattr(self, "embedding_model") and self.embedding_model:
            # Call your embedding model here
            return self.embedding_model.embed(text)
        # Fallback: None (disables semantic search)
        return None

    def _probe_impl(self) -> ProbeResult:
        if self.provider == "openai":
            probe_result = probe_openai(self.base_url, self.api_key, self.timeout_seconds)
        else:
            probe_result = probe(self.provider, self.base_url, self.timeout_seconds)
        if not probe_result.ok:
            self.logger.log("ERROR", "LLM probe failed", reason=probe_result.reason)
            env = build_error_envelope(
                code="NETWORK_ERROR" if "Network error" in (probe_result.reason or "") else "PROVIDER_ERROR",
                message=f"LLM startup probe failed: {probe_result.reason}",
                component="Core/LLM",
                suggestion="Check network, base_url, and API credentials",
            )
            emit_error(env)
            return probe_result
        self.logger.log("INFO", "LLM probe succeeded")
        return probe_result

    def _generate_impl(self, prompt: str, **kwargs):
        stream = bool(kwargs.get("stream", False))
        if self.provider == "echo":
            if stream:
                return generate_echo_stream(prompt, self.model)
            return generate_echo(prompt, self.model, **kwargs)
        if self.provider == "openai":
            return generate_openai(prompt, self.model, self.base_url, self.api_key, **kwargs)
        return {"provider": self.provider, "model": self.model, "output": f"(stub) {prompt}"}
