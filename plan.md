# Nestify — App Planning

## Vision & Goals
- Purpose: Describe the problem Nestify solves and why it matters.
- Goals: 3–5 measurable outcomes for the first release.
- Audience: Primary users and their key needs.

## Target Users & Use Cases
- Personas: Who uses it and what they do.
- Core use cases: Top tasks the app must support.

## MVP Scope
- Must-have features: Minimal set to deliver value.
- Nice-to-have: Deferred features for later iterations.
- Non-goals: Explicitly out-of-scope items for MVP.

## Architecture Overview (Python)
- Runtime: Python version (e.g., 3.11).
- Framework: FastAPI/Django/Flask (decide one).
- Persistence: PostgreSQL/SQLite, ORM (SQLAlchemy/Django ORM/Pydantic models).
- Auth: JWT/OAuth2/Session-based.
- Integrations: External APIs/services, messaging, caching (Redis).
- Deployment: Containerized (Docker), CI, hosting targets.

## Tech Stack Decisions
- Python: Version and packaging (pyproject.toml).
- Web framework: Pros/cons and decision.
- Database: Schema, migrations, backups.
- Testing: Pytest, coverage, structure.
- Tooling: Linters (ruff), formatter (black), type checking (mypy).

## Data Model (Draft)
- Entities: List core models and relationships.
- Example tables:
  - Users: id, email, password_hash, roles, created_at
  - Items: id, owner_id, title, status, created_at
  - Activity: id, actor_id, target_id, type, metadata, ts

## API Design (Draft)
- Auth: /auth/register, /auth/login, /auth/refresh
- Users: /users/me, /users/{id}
- Items: /items, /items/{id}
- Activity: /activity, filters & paging
- Conventions: REST/JSON, pagination, error format, versioning (/v1).

## Milestones & Timeline
- Milestone 1: MVP scaffolding, auth, basic CRUD.
- Milestone 2: Data model, tests, CI, containerization.
- Milestone 3: Observability, performance, first deployment.

## Risks & Assumptions
- Risks: Scope creep, auth complexity, data migration.
- Assumptions: Single region, moderate traffic, standard compliance needs.

## Success Metrics
- Activation rate, task completion time, error rate, latency.

## Open Questions
- Which framework? FastAPI vs Django.
- Multi-tenant requirements?
- Deployment target and budget?

## Next Steps
- Decide framework and DB.
- Scaffold project (src/, tests/, pyproject.toml).
- Establish env management and secrets handling.
- Draft initial data model and endpoints.
