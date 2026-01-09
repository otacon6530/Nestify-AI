from __future__ import annotations
import requests
from .llm_probe import ProbeResult


def probe_openai(base_url: str | None, api_key: str | None, timeout_seconds: int) -> ProbeResult:
    if not base_url:
        return ProbeResult(False, "Missing base_url for OpenAI provider")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = base_url.rstrip("/") + "/models"
    try:
        r = requests.get(url, headers=headers, timeout=timeout_seconds)
        if 200 <= r.status_code < 300:
            return ProbeResult(True)
        return ProbeResult(False, f"Status {r.status_code}")
    except Exception as e:
        return ProbeResult(False, f"Network error: {e}")


def generate_openai(prompt: str, model: str, base_url: str | None, api_key: str | None, **kwargs):
    stream = bool(kwargs.get("stream", False))
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"} if api_key else {"Content-Type": "application/json"}
    if stream:
        # Encourage SSE streaming from compatible servers
        headers["Accept"] = "text/event-stream"
    url = (base_url or "").rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": stream}
    r = requests.post(url, json=payload, headers=headers, timeout=60, stream=stream)
    r.raise_for_status()
    if stream:
        def gen():
            collected = []
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    evt = requests.utils.json.loads(line)
                except Exception:
                    continue
                # Try common OpenAI-style delta paths
                token = (
                    evt.get("choices", [{}])[0].get("delta", {}).get("content")
                    or evt.get("choices", [{}])[0].get("message", {}).get("content")
                    or evt.get("content", "")
                    or evt.get("response", "")
                )
                # Some servers emit content as arrays of parts
                if not token:
                    parts = evt.get("content")
                    if isinstance(parts, list):
                        buf = []
                        for p in parts:
                            if isinstance(p, dict) and p.get("type") == "text":
                                buf.append(p.get("text", ""))
                            elif isinstance(p, str):
                                buf.append(p)
                        token = "".join(buf)
                # Some servers use choices[].text
                if not token:
                    ch0 = evt.get("choices", [{}])[0]
                    if isinstance(ch0, dict):
                        token = ch0.get("text", "") or ch0.get("delta", {}).get("content", "")
                if token:
                    collected.append(token)
                    yield {"type": "token", "value": token}
            full_text = "".join(collected)
            yield {"type": "final", "result": {"text": full_text, "model": model, "usage": {}}}
        return gen()
    data = r.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"provider": "openai", "model": model, "output": text, "usage": data.get("usage", {})}
