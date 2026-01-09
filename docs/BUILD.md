# Build & Install (Windows)

- Create venv:
  - `python -m venv .venv`
  - `.\.venv\Scripts\Activate.ps1`
- Editable install:
  - `python -m pip install -U pip`
  - `python -m pip install -e .`
- Run:
  - `nestify exec "hello world"`
  - `nestify run`
  - `nestify shell "echo hi"`
- Logs: `%LOCALAPPDATA%/Nestify/logs/log.jsonl`
