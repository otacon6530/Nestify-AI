# Nestify

Core + CLI scaffolding is implemented.

- Exec: `nestify exec "hello world"`
- Run (streaming): `nestify run`
- Shell with approvals: `nestify shell "dir"`

Configuration: see config.yaml. You can set environment overrides: `NESTIFY_PROVIDER`, `NESTIFY_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`.

Logs: `%LOCALAPPDATA%/Nestify/logs/log.jsonl`.
# Nestify

Basic project initialization.

## Getting Started

1. Ensure Git is installed.
2. Clone or open this folder.
3. Optional: create an `.env` or `.env.local` for local configs.

## What’s Included

- Generic `.gitignore` covering OS/editor artifacts, logs, env files, Node, and Python.
- Minimal README.

## Next Steps

- Decide on tech stack (e.g., NestJS, Python, etc.).
- Add project scaffolding (e.g., `src/` structure) and tooling.
- Initialize package manager or virtual environment as needed.
