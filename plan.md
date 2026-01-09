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

### Class Specifications
1. `Config`
  - Responsibility: Load and validate all configuration required to run the app.
  - Sources: Reads `config.yaml`; supports environment variable overrides.
  - Provides: Accessors for model provider settings, API keys, cache paths, runtime flags.

2. `Logger`
  - Responsibility: Multi-level logger with file output.
  - Output: Writes to `log.txt` by default; supports levels (DEBUG/INFO/WARN/ERROR).
  - Options: Consider rotation or size limits in future versions.

3. `LLM`
  - Responsibility: Communicate with OpenAI-compatible APIs.
  - Interface: Adapter-based provider support; method like `generate(prompt, config) -> Result`.
  - Config: Reads provider name, model, API key from `Config`.

4. `Memory`
  - Responsibility: Vector-based memory manager for storing and retrieving context.
  - Backend: Pluggable (e.g., local embeddings + FAISS-like store) for v0.0.1 simple local implementation.
  - API: `add(text, metadata)`, `search(query, top_k)`.

5. `ToolManager`
  - Responsibility: Import tools from `tools/`, register them, and provide invocation.
  - Scope: Tools in `tools/` are globally available; support tagging to mark app-specific tools (e.g., VS Code-only).
  - Metadata: Pass structured metadata/context into tool calls; integrate tools provided by `MCP`.

6. `SkillsManager`
  - Responsibility: Load and use OpenAI structured skills from `skills/`.
  - API: Register skills, validate schemas, expose skills to `LLM` or `Agent` workflows.

7. `MCP`
  - Responsibility: Connect to an MCP server and consume its tools.
  - Integration: Feed discovered tools into `ToolManager` for unified invocation.

8. `Agent`
  - Responsibility: Manage system prompts and agent behaviors; load agent definitions from `agents/`.
  - Config: Assign agents to tasks via configuration (tools may define tasks).
  - API: `prepare_context(task, config, memory) -> PromptContext`.

### Communication Constraints
- `core.py` is the orchestration layer:
  - Instantiates `Config`, `Logger`, `LLM`, `Memory`, `ToolManager`, `SkillsManager`, `MCP`, and `Agent`.
  - Wires instances together by passing references only within `core.py`.
  - Other classes remain loosely coupled and unaware of each other beyond their public interfaces.

### Example Flow
1. `core.py` loads `Config` and initializes `Logger`.
2. Initialize `LLM` with provider settings; initialize `Memory`.
3. `ToolManager` loads tools from `tools/` and `MCP` adds remote tools.
4. `SkillsManager` loads skills; `Agent` selects system prompt based on task.
5. Execute a task: `Agent` prepares context; `LLM` generates; `ToolManager` handles tool calls; `Memory` stores relevant artifacts; `Logger` records events.

## Tech Stack Decisions
- Python: 3.11+, `pyproject.toml` for packaging and dependencies
- CLI: `typer` or `argparse` for commands; rich for output formatting
- VS Code: TypeScript extension using the VS Code API, communicating with CLI/core
- Testing: `pytest` with unit tests for core abstractions and CLI commands
- Tooling: `ruff` (lint), `black` (format), `mypy` (types), `pre-commit`

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
  - `nestify run <prompt_file> [--model ...] [--vars ...]`
  - `nestify eval <runs_dir> [--metric ...]`
  - `nestify config set/get <key> [value]`
- VS Code Extension:
  - Commands: Run current file, show output panel, toggle model/config
  - Settings: Model, API key, cache dir

## Milestones & Timeline
- Milestone 1 (Core & CLI): Scaffolding, basic `ModelClient`, `Executor`, `nestify run/config`, tests
- Milestone 2 (VS Code): Command palette actions, output panel, settings integration
- Milestone 3 (Quality): Eval tooling basics, pre-commit hooks, docs, packaging & version bump

## Risks & Assumptions
- Risks: Scope creep, auth complexity, data migration.
- Assumptions: Single region, moderate traffic, standard compliance needs.

Additional Risks (LLM-specific): Provider API changes, rate limits, prompt injection, dependency on API keys.

## Success Metrics
- Developer activation (runs per day), iteration speed, eval coverage, error rate, latency/cost per generation.

## Open Questions
- Which primary provider(s) to support first?
- CLI vs extension communication path (direct Python bridge vs CLI invocation)?
- Config format preference (YAML vs TOML vs JSON)?

## Next Steps
- Create Python core skeleton (`nestify_core`) with `ModelClient`, `Executor`, and config loader
- Scaffold CLI (`nestify`) with `run` and `config` commands
- Initialize VS Code extension structure and command palette entries
- Set up tooling: ruff, black, mypy, pytest, pre-commit
- Define `pyproject.toml`, basic dependency set, and version `0.0.1`
