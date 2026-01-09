from nestify_core.classes.config import Config
from nestify_core.classes.llm import LLM

def test_llm_probe_echo_ok(monkeypatch):
    monkeypatch.setenv("NESTIFY_PROVIDER", "echo")
    cfg = Config()
    llm = LLM(cfg)
    res = llm.probe()
    assert res.ok
