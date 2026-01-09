# Nestify — LLM App Planning (v0.0.1)

Nestify is an LLM-powered application starting at version **0.0.1**. The system is divided into three parts:

1) Core (Python library) — foundational LLM utilities, abstractions, and runtime
2) Command Line Tool (CLI) — developer/operator interface for workflows
3) Visual Studio Code Extension — in-editor experience powered by the core

## Vision & Goals
- Purpose: Provide a cohesive toolkit and UX to build, run, and iterate on LLM workflows efficiently.
- Goals (v0.0.1):
  - Ship a usable Python core with prompt/executor abstractions and basic tool/chain support
  - Provide a CLI for running prompts, evaluating outputs, and managing configs
  - Deliver a VS Code extension enabling quick runs, result inspection, and config editing
- Audience: Developers building LLM-backed features, analysts evaluating outputs, and operators maintaining workflows.

## Target Users & Use Cases
- Personas:
  - LLM Developer: Creates prompts, chains, tools; iterates quickly
  - ML/QA Analyst: Reviews outputs, applies heuristics/metrics, compares runs
  - Operator: Manages environment variables, keys, and deployment configs
- Core Use Cases (v0.0.1):
  - Configure models/keys and run prompts locally
  - Inspect outputs, tokens, and basic cost metrics
  - Save runs and diffs to files for comparison
  - Edit configs and prompts in VS Code and re-run

## MVP Scope (v0.0.1)
- Must-have:
  - Core: `Prompt`, `ModelClient` interface, `Executor` for single calls, config loader, simple caching
  - CLI: `nestify run`, `nestify eval`, local config management (`nestify config set/get`)
  - VS Code: Run current prompt, show output panel, minimal settings UI
- Nice-to-have (defer):
  - Dataset-driven evaluations, multi-model comparisons, telemetry/O11y
  - Advanced prompt tooling (templating DSLs), multi-tenant support
- Non-goals (for v0.0.1):
  - Server-side orchestration, distributed runs, complex RBAC

## Architecture Overview
- Runtime: Python 3.11+
- Packaging: `pyproject.toml` (Poetry/PDM/PEP 621), core as installable lib
- Integrations: OpenAI-compatible APIs; pluggable model providers (adapter interface)
- Storage: Local filesystem for runs/configs; optional cache dir
- VS Code: Extension communicates via Node/TypeScript, invokes Python core via CLI or Python bridge
- CI: Linting (ruff), formatting (black), type checks (mypy), tests (pytest)

## Core Design (v0.0.1)
- Entry point: `core.py` orchestrates initialization and is the only place where class instances communicate with each other. Other modules must not directly depend on or call each other; they expose interfaces consumed by `core.py`.
- Classes location: `classes/` folder contains all class definitions for the application.
- Additional folders:
  - `tools/`: Built-in and app-specific tools (e.g., VS Code-specific tools)
  - `skills/`: OpenAI structured skills definitions
  - `agents/`: Agent definitions with system prompts
  - `functions/`: All class function implementations live here and are imported into classes, then bound as methods during class initialization.

### Method Binding Pattern
- All functions that implement class behaviors are defined in `functions/`.
- Each class in `classes/` imports the relevant functions and assigns them to the class instance in its `__init__`, making them available as methods.
- This keeps function implementations reusable and decoupled, while `core.py` remains the sole orchestrator of inter-class communication.
 - Function granularity: Every function must live in its own file under `functions/` (for both Core and CLI). Use clear, descriptive file names (snake_case) that match the function’s purpose.

### Class Specifications
1. `Config`
  - Responsibility: Load and validate all configuration required to run the app.
  - Sources: Reads `config.yaml`; supports environment variable overrides.
  - Provides: Accessors for model provider settings, API keys, cache paths, runtime flags.

2. `Logger`
  - Responsibility: Multi-level logger with file output.
  - Output: Writes to `log.txt` by default; supports levels (DEBUG/INFO/WARN/ERROR).
  - Fields: datetime, level, file, line, message.
  - Rotation: Size-based rotation (default max size 10 MB, retain 5 files).
  - Location (Windows): %LOCALAPPDATA%/Nestify/logs/.
  - Format: JSON Lines (JSONL), one event per line for machine-readable logs.

3. `LLM`
  - Responsibility: Communicate with OpenAI-compatible APIs.
  - Interface: Adapter-based provider support; method like `generate(prompt, config) -> Result`.
  - Config: Reads provider name, model, API key from `Config`.
  - Streaming: Default behavior is token streaming end-to-end. The CLI `nestify run` and VS Code extension stream outputs; `nestify exec "<text>"` does not stream and returns a single final result.
  - Startup Connectivity Probe: On application startup, perform a health check to the configured LLM provider (e.g., a lightweight request such as `models.list` or a minimal `echo` call). If unreachable or unauthorized, fail fast by emitting a unified error envelope and exiting with an appropriate code (NETWORK_ERROR for connectivity/DNS/timeouts; PROVIDER_ERROR for authentication/invalid config). Include a configurable timeout (default 5s) and a single optional retry with short backoff; log the probe result.

4. `Memory`
  - Responsibility: Vector-based memory manager for storing and retrieving context.
  - Backend: Pluggable (e.g., local embeddings + FAISS-like store) for v0.0.1 simple local implementation.
  - API: `add(text, metadata)`, `search(query, top_k)`.

5. `ToolManager`
  - Responsibility: Import tools from `tools/`, register them, and provide invocation.
  - Scope: Tools in `tools/` are globally available; support tagging to mark app-specific tools (e.g., VS Code-only).
  - Metadata: Pass structured metadata/context into tool calls; integrate tools provided by `MCP`.
  - Approvals: Sensitive tools (e.g., `shell`) are registered with `requires_approval=true`; execution is gated until explicit user approval.

6. `SkillsManager`
  - Responsibility: Load and use OpenAI structured skills from `skills/`.
  - API: Register skills, validate schemas, expose skills to `LLM` or `Agent` workflows.
  - Shell Skill: Expose a structured `shell` skill backed by `tools/shell.py`; marked sensitive and requires approval before any execution.

7. `MCP`
  - Responsibility: Connect to an MCP server and consume its tools.
  - Integration: Feed discovered tools into `ToolManager` for unified invocation.

8. `Agent`
  - Responsibility: Manage system prompts and agent behaviors; load agent definitions from `agents/`.
  - Config: Assign agents to tasks via configuration (tools may define tasks).
  - API: `prepare_context(task, config, memory) -> PromptContext`.

9. `ArgManager`
  - Responsibility: Parse and validate core arguments independent of the CLI framework; provide consistent usage/help for both CLI and VS Code.
  - Interface: parse(argv) -> Args; usage() -> str; validate(args) -> None | ErrorEnvelope.
  - Supported Args: --help; exec "<text>" (single execute payload).
  - Behavior: Returns structured Args with mode, message, and a correlation_id; invalid inputs yield ErrorEnvelope with code=INVALID_ARGUMENT.
  - Integration: CLI delegates to ArgManager to ensure consistent parsing/validation across surfaces.

### Communication Constraints
- `core.py` is the orchestration layer:
  - Instantiates `Config`, `Logger`, `LLM`, `Memory`, `ToolManager`, `SkillsManager`, `MCP`, and `Agent`.
  - Wires instances together by passing references only within `core.py`.
  - Other classes remain loosely coupled and unaware of each other beyond their public interfaces.

### Error Handling & Unified Envelope
- `core.py` wraps end-to-end orchestration in a single try block. Any uncaught exception is captured and emitted as a standardized error envelope consumable by both the CLI and VS Code extension.
- Error Envelope Schema:
  - code (string), message (string), component (string), stack (string[]), timestamp (ISO 8601), correlation_id (string), suggestion (string | null)
- Transport:
  - CLI: prints the envelope as JSON to stderr and maps to exit codes
  - VS Code: returns the envelope over IPC to the extension
- Exit Code Mapping:
  - 0 OK; 1 UNKNOWN; 2 INVALID_ARGUMENT; 3 CONFIG_ERROR; 4 NETWORK_ERROR; 5 PROVIDER_ERROR; 6 PERMISSION_DENIED; 7 TIMEOUT
- Logging: The envelope is logged by Logger with level=ERROR as a JSONL event.

### Example Flow
1. `core.py` loads `Config` and initializes `Logger`.
2. Initialize `LLM` with provider settings; initialize `Memory`.
3. Probe LLM connectivity immediately: perform the startup health check and either continue on success or emit a unified error envelope and exit early on failure.
4. `ToolManager` loads tools from `tools/` and `MCP` adds remote tools.
5. `SkillsManager` loads skills; `Agent` selects system prompt based on task.
6. Execute a task: `Agent` prepares context; `LLM` generates; `ToolManager` handles tool calls; `Memory` stores relevant artifacts; `Logger` records events.

## Tech Stack Decisions
- Python: 3.11+, `pyproject.toml` for packaging and dependencies
- CLI: `typer` or `argparse` for commands; rich for output formatting
- VS Code: TypeScript extension using the VS Code API, communicating with CLI/core
- Testing: `pytest` with unit tests for core abstractions and CLI commands
- Tooling: `ruff` (lint), `black` (format), `mypy` (types), `pre-commit`
 - Tests layout: `tests/` with `tests/functions/` and `tests/classes/` to mirror implementation areas.

## Data Model (Draft)
- Entities: List core models and relationships.
- Example tables:
  - Users: id, email, password_hash, roles, created_at
  - Items: id, owner_id, title, status, created_at
  - Activity: id, actor_id, target_id, type, metadata, ts

Note: For v0.0.1, prefer local file storage (YAML/JSON) for configs and run logs over a database.

## API Design (Draft)
- Core Python interfaces:
  - `ModelClient`: `generate(prompt: str, **kwargs) -> Generation`
  - `Prompt`: content, variables, render()
  - `Executor`: run(prompt, model, config) -> Result
  - `ProviderAdapter`: OpenAI/others; configurable via environment and config files
- CLI commands (initial):
  - `nestify exec "<text>"`
  - Streaming behavior: `run` streams by default (offer `--no-stream` to disable); `exec` never streams.
  - Session Modes:
    - Continuous Chat (default): interactive, streaming tokens as they arrive; input gated until final response to maintain parity with the extension
    - One-and-Done Exec: `nestify exec "<text>"` performs a single execution without establishing a chat session, returns a final non-streamed result
  - Core Bridge & UX Parity:
    - Uses the Python Core directly (no intermediate server) and emits the same unified error envelope as the VS Code extension
    - Chat semantics mirror the extension: single-message send is gated until final response; show a spinner/progress indicator while the Core is working
    - Mode selection equivalent to the extension dropdown via `--mode default|plan` (Default is the default)
    - Input is blocked until the final assistant response is printed; spinner/progress stops upon completion
- VS Code Extension:
  - Commands: Run current file, show output panel, toggle model/config
  - Settings: Model, API key, cache dir
  - Streaming: Streams tokens by default to the output panel; adheres to the same non-stream policy for `exec`.
  - Core Bridge: Uses a Python bridge to interact with the Core directly (preferred over CLI invocation) for lower latency and richer IPC.
  - Chat UI:
    - Layout: A chat view with a message box at the bottom
    - Left of message box: a dropdown with options `Default` and `Plan`
    - Right of message box: a Send button
    - Send behavior: when a message is sent, the Send button becomes grey (disabled) and prevents additional sends until the final assistant response is received from the Core and rendered
    - Work-in-progress indicator: while the Core is working, show a spinning circle in the active chat line
    - Completion: once the final response is displayed, remove the spinner and re-enable the Send button

## CLI Design (v0.0.1)
- Entry point: `main.py` orchestrates CLI logic and is the only place where CLI class instances communicate with each other, mirroring the Core’s `core.py` orchestration.
- Folders:
  - `classes/`: CLI-specific classes (e.g., `ArgManager`, session handlers)
  - `functions/`: Reusable function implementations bound to CLI classes during initialization
  - `tests/classes/` and `tests/functions/`: Test layout mirroring the implementation structure
- Behavior Parity:
  - Uses the Python Core via bridge; unified error envelope; streaming defaults for continuous chat
  - `nestify exec "<text>"` performs a one-and-done execution (non-stream)
  - Mode selection via `--mode default|plan`; input gating and progress spinner semantics match the VS Code extension

## Shell Skill & Approval Workflow
- Location: All shell logic resides in `tools/shell.py`. The `shell` skill allows the AI to request execution of local shell commands and is marked sensitive.
- Per-command approval: Each requested `shell` command requires explicit user approval before it executes.
- Deny behavior: If denied, a structured denial result is returned so the LLM is aware of the denial and can replan.
- Approve All: Users may select “Approve All” to allow all subsequent `shell` commands for the current session; approvals reset when the session resets or mode changes.
- Session scope: A session is one continuous chat in the extension or a single CLI run; new sessions reset approvals.
- CLI UX: The CLI prints the full command and prompts: Approve, Deny, Approve All. Input is gated until a decision. On Approve, output streams line-by-line in interactive runs; on Deny, a denial message is printed and returned.
- VS Code UX: An inline approval banner shows the command with Approve/Deny/Approve All. The Send button remains disabled until a decision; a spinner shows during execution and is removed on final result.
- Logging & safety: Logger records approval requests/decisions, sanitized command, exit code, duration, truncated outputs, and correlation_id. Commands have a default timeout (e.g., 30s) and may run in a restricted working directory. Secrets are redacted in all logs.
- Windows specifics: Default shell is PowerShell (configurable fallback to cmd.exe). Quoting/escaping follows PowerShell rules; the tool respects current execution policies.

## Documentation
- Build Document: Provide a dedicated build document detailing how to build, install, and run the Core, CLI, and VS Code extension (Windows-focused; include PowerShell examples and `scripts/build.ps1` usage).
- READMEs: Maintain component-specific READMEs with instructions and descriptions:
  - Core README: installation, configuration (`config.yaml`), Logger behavior, error envelope
  - CLI README: commands (`run`, `eval`, `config`, `exec`), streaming behavior, session modes, examples
  - VS Code Extension README: installation steps, settings, Python bridge usage, chat UI and UX semantics
  - Root README: overview, architecture, quick start, links to component docs

## Milestones & Timeline
- Milestone 1 (Core & CLI): Scaffolding, basic `ModelClient`, `Executor`, `nestify run/config`, tests
- Milestone 2 (VS Code): Command palette actions, output panel, settings integration
- Milestone 3 (Quality): Eval tooling basics, pre-commit hooks, docs, packaging & version bump

