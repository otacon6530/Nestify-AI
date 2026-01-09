from nestify_core.classes.config import Config
from nestify_core.classes.llm import LLM
from nestify_core.classes.logger import Logger

def test_llm_probe_echo_ok(monkeypatch):
    monkeypatch.setenv("NESTIFY_PROVIDER", "echo")
    cfg = Config()
    logger = Logger()
    llm = LLM(cfg, logger)
    res = llm.probe()
    assert res.ok
