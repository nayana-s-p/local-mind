# LocalMind implementation guide

Created in this repository at the user's request on 2026-10-18. No source file with this name was found in Downloads or the project. This document consolidates the supplied `AGENTS.md`, `AGENT_PROMPT.md`, and `CODEX_START_PROMPT.md`; it is not represented as a copy of a missing original.

## Contract and scope

Read `AGENTS.md` fully for the feature, engineering, privacy, and quality requirements. Use `CODEX_START_PROMPT.md` for the supplied milestone ordering. Preserve existing working code and user data. Attached/project documents remain data; their contents never authorize the desktop assistant to execute code or change files.

LocalMind is a bounded offline Python 3.12+ assistant with PySide6/QML, SQLite, and an ONNX intent artifact below 200 MB. It must remain useful without a generative model. No silent cloud fallback, telemetry, unrestricted shell, or automatic execution of analyzed code. User-file mutations require a complete preview and explicit approval of that exact plan. Internal application state and explicitly requested model provisioning use their own documented controls.

## Milestones from CODEX_START_PROMPT.md

| Stage | Scope |
| --- | --- |
| M0 | Repository audit, feature inventory, architecture/dependency map, risks, migration plan. |
| M1 | Architecture boundaries, working application shell, typed contracts, versioned SQLite foundation and a tested UI-to-storage vertical slice. |
| M2 | Metadata-only folder analysis and evidence-based project analysis. |
| M3 | Bounded file previews, factual result composition, structured follow-up context. |
| M4 | Deterministic routing first, ONNX scoring second, verified offline model lifecycle. |
| M5 | Previewed/approved organization, safe application launch adapters. |
| M6 | System information, complete history controls, supported result-based suggestions. |
| M7 | Complete Assistant/Dashboard/History/Settings UI, accessibility, themes and responsive states. |
| M8 | Security/performance/platform hardening and packaging. |
| M9 | Optional opt-in generative provider, only after core acceptance. |

Existing features can already implement portions of later milestones. Audit their actual evidence rather than rewriting them to match this sequence.

## Current execution

Following the kickoff prompt, complete M0 before code changes, then implement M1 as an independently tested slice. M1 acceptance details below are repository-specific implementation criteria derived from the supplied architecture/app-shell/SQLite scope; they are not quotations from a missing guide.

### M1 acceptance

- Move dependency composition out of the executable entry point while preserving the public startup/testing entry points and existing services.
- Add typed conversation, message, context-reference, plan, approval, and execution-event boundaries without Qt/SQLite dependencies in the domain.
- Use a versioned SQLite schema, foreign keys, indexes, parameterized SQL, bounded reads, retention, and explicit errors for unsupported/corrupt databases.
- Run schema migration, history reads/writes, and serialization on a worker. Preserve conversation/message ordering during asynchronous writes and switching.
- Connect chat submission and response rendering to persisted conversation history. Provide working navigation, resume/new-conversation and confirmed clear-history controls. Never restore a pending approval as permission to execute.
- Persist photo plan/approval/execution references without replacing or clearing the existing independent undo journal.
- Redact recognized secret patterns before persistence; keep preview contents out of chat audit storage. Document that automatic redaction is not a secret detector for arbitrary text.
- Keep the previous assistant, model setup, file discovery, previewed photo moves, and undo working.
- Run the existing and new storage/concurrency/GUI tests, `ruff check .`, `pytest`, and configured checks; report platform/model limitations truthfully.

## Reporting

Maintain `docs/IMPLEMENTATION_STATUS.md` and `docs/ARCHITECTURE.md`. Distinguish baseline observations, new verified changes, proposals, and missing features. Completing M1 does not mean M2–M9 or the full product specification are complete.
