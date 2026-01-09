# Codex Chat VS Code Extension

Codex Chat adds a webview panel inside Visual Studio Code that talks to the existing Python backend (`core/chat_process.py`). It lets you open a chat session, toggle debug metrics, list tools, and reset the conversation without leaving the editor.

## Prerequisites

- Python 3.10+ available on your system PATH, or configure the Python executable in the extension settings.
- Codex project dependencies installed (run `pip install -r requirements.txt` from the repository root).
- VS Code 1.85.0 or newer.

## Configuration

Open **Settings > Extensions > Codex Chat** (or search for `codexChat`):

- `codexChat.workspacePath`: Directory used as `cwd` for the Python backend. Leave empty to reuse the first folder in the current VS Code workspace.
- `codexChat.pythonPath`: Python executable path. Defaults to `python`.

Environment variable override: set `CODEX_AGENT_ROOT` if you need to point the backend at a different checkout than the opened workspace.

## Running from Source

1. Open the `VSCodeExtension/codex-chat` folder in VS Code.
2. Run `npm install` to fetch the packaging dependency (`vsce`).
3. Launch the extension host: press `F5` or run the **Run Extension** launch configuration.
4. In the Extension Development Host window, run the command **Codex Chat: Open**.

The panel shows connection status, enables controls once the Python backend reports `ready`, and streams assistant/debug messages as they arrive.

## Packaging

To create a `.vsix` package run:

```sh
npm run package
```

Install the resulting file with `code --install-extension codex-chat-*.vsix`. Restart VS Code for the extension to activate.

## Known Limitations

- Only one chat panel can run at a time; reopening focuses the existing panel.
- The backend must remain compatible with the JSON protocol emitted by `core/chat_process.py`.
- Debug output is appended verbatim; large payloads are not batched.
