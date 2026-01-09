# Nestify

Core + CLI implemented; VS Code extension scaffold with Python bridge.

## Quick Start (Windows, PowerShell)
- Create/activate venv and install:
	- `.\.venv\Scripts\Activate.ps1`
	- `& "G:\Dev\Nestify\.venv\Scripts\python.exe" -m pip install -e .`
- Run CLI:
	- Chat (streaming): `nestify run`
	- Exec (non-stream): `nestify exec "hello world"`
	- Shell with approvals: `nestify shell "echo hi"`
- If `nestify` isn’t on PATH after activation:
	- `& "G:\Dev\Nestify\.venv\Scripts\python.exe" -m nestify_cli.main run`

## Configuration
- Edit [config.yaml](config.yaml) or use env vars: `NESTIFY_PROVIDER`, `NESTIFY_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`.
- For a quick streaming check, set `llm.provider: echo` and `llm.model: local-echo`.
- OpenAI-compatible servers: ensure `/chat/completions` supports `stream: true`.

## Logs
- JSONL logs: `%LOCALAPPDATA%/Nestify/logs/log.jsonl`.

## VS Code Extension
- Folder: [vscode-extension](vscode-extension)
- Setup:
	- `Set-Location G:\Dev\Nestify\vscode-extension`
	- `npm install`
	- `npm run watch`
	- Press F5 in VS Code to launch the Extension Development Host
	- Command Palette: “Nestify: Open Chat”
	- Settings: set `nestify.pythonPath` to your venv Python (e.g., `G:/Dev/Nestify/.venv/Scripts/python.exe`)

## Build & Docs
- See [docs/BUILD.md](docs/BUILD.md) for build and test steps.

## Notes
- If streaming doesn’t show tokens, try echo provider or verify your server’s SSE format.
- If PATH issues prevent `nestify` from running, use the module form shown above.
