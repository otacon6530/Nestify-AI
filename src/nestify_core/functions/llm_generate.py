from __future__ import annotations


def generate_echo(prompt: str, model: str, **kwargs) -> dict:
    return {
        "provider": "echo",
        "model": model,
        "output": f"ECHO: {prompt}",
        "usage": {"input_tokens": len(prompt.split()), "output_tokens": len(prompt.split())},
    }


 def generate_echo_stream(prompt: str, model: str):
     for w in prompt.split():
         yield {"type": "token", "value": w + " "}
     yield {"type": "final", "result": {"text": prompt, "model": model, "usage": {}}}
