# LocalMind architecture

## Observed baseline

`__main__.py` assembles scanners, local model installer/classifier, OS adapters, photo organizer, and two view models. QML calls typed Qt slots. Assistant workers return decisions/plans/results; file discovery has its own worker. The photo adapter owns a separate durable SQLite undo journal. Chat, context and recent activity are in memory.

Dependencies flow from presentation to application/domain, and infrastructure implements application ports. Domain modules have no Qt, ONNX or SQLite dependencies. All actual user-file moves pass through a typed preview, explicit approval and immediate identity/path revalidation.

## Implemented M1 architecture

Assembly now lives in `bootstrap/`. The executable owns Qt startup/lifecycle and retains the existing `create_view_models` import for callers. Typed history entities and a repository port separate persistence from Qt and SQLite.

`QML → AssistantViewModel → HistoryViewModel → serialized worker → conversation use case → history repository port → SQLite adapter`.

The History view model owns a single worker queue. Initialization, migration, retention, serialization, writes, queries and conversation switching are ordered on that queue. Normal message writes do not block the composer. Switching conversations temporarily disables action submission and cannot run during an active action. Errors are surfaced as storage errors without fabricating failed/successful desktop actions.

SQLite stores conversations, messages, structured context references, action plans, approvals, events and settings. Use schema versions, WAL, foreign keys, indexes, parameterized SQL, bounded query limits, and transaction rollback. Unknown newer schemas or corrupt files fail visibly; never reset them automatically.

Persisted history is data. Reopening a conversation must clear live pending approvals and follow-up execution state. Context references do not authorize access to a workspace or replay actions. Photo undo remains the existing independent journal; clearing or expiring chat must not destroy undo capability.

## Privacy and migration

Redact recognized credentials/tokens before storing messages and audit summaries. Avoid file preview bodies in persistent chat. Provide bounded retention and a confirmed clear-history action. This is local plaintext application storage, not encrypted secret storage; arbitrary secrets cannot be reliably inferred from text.

Create the new history schema independently of existing photo journals and model directories. Never migrate image files during startup. Source/project documents are untrusted data and are never executable instructions for the desktop agent.

## Concrete modules and lifecycle

- `domain/history.py`: stored messages, conversation summaries, immutable snapshots and typed storage errors.
- `application/ports.py`: conversation repository protocol alongside the preserved tool protocols.
- `application/use_cases/conversation_history.py`: history startup, new/clear and retention validation.
- `infrastructure/persistence/history.py`: schema-v1 migration, secret-pattern redaction, bounded retention/reads, active-conversation persistence, plan/approval/event storage.
- `presentation/history_viewmodel.py`: a single-thread worker queue, captured conversation IDs, asynchronous switching and user-confirmed destructive history controls.
- `presentation/assistant_viewmodel.py`: renders restored messages and records actual conversations/actions without replaying historical authorization.
- `presentation/qml/pages/HistoryPage.qml` and `DashboardPage.qml`: real persisted records and current service/session state. `SetupPage.qml` is exposed through Settings.

Startup migrates/opens history on its worker before enabling conversation submission. Message writes are queued without blocking the composer. Switching is serialized after prior writes and guarded against active desktop tasks. An older selected conversation is recorded separately from most-recently-updated ordering so restart restores the selected conversation. Shutdown drains storage writes; interrupted approval state expires on the next start rather than becoming executable.

Photo filesystem recovery continues to use its independent journal. History clearing cascades only conversation-owned records and leaves that undo journal and model cache intact. There was no prior durable conversation schema to migrate; existing in-memory chats cannot be backfilled from an older running process.

## Historical M1 boundary

M1 supplied architecture, a working shell, and persistence. At the close of M1, folder/project reports, previews, metrics and suggestions were deferred. The task-catalog expansion below implements these slices. Complete theme/accessibility coverage and native platform packaging remain unfinished.

## Task catalog implementation

The catalog expansion now implements the folder/project/preview/system and safe general-file slices previously listed as future milestones. `docs/TASK_CATALOG_IMPLEMENTATION.md` is the current support matrix.

`Composer → AssistantViewModel → InterpretAssistantRequest → deterministic slot extraction / local ONNX retrieval → typed TaskRequest → RunTasks → TaskRegistry → injected tool service → TaskBatchResult → factual messages, result cards, live context and supported suggestions`.

The registry contains only installed handlers. Parameter names/types/lengths are validated before dispatch. Write handlers can return only immutable `FilePlan` previews; commit is a separate API gated by the exact plan ID from an explicit button/chat approval. The runner executes no more than six steps and stops at the first preview or failure. Later actions do not resume automatically after approval. Unsupported action combinations ask for separate requests.

Six shared services implement folder metadata queries, project evidence, text/JSON/CSV previews, scoped file changes, allowlisted desktop handoff and psutil snapshots. The ONNX adapter has additional semantic families for these tools. Deterministic requests work without inference; low-confidence semantic predictions ask for clarification. Neither route can emit shell commands or authorize file mutation.

Live context holds bounded result metadata, the authorized scope, up to 100 file references, current result summary and pending clarification. New scopes clear file references. History restoration clears all live targets, cards, suggestions, and approval; storage does not replay actions. Preview bodies/README excerpts are excluded from persisted chat/events, including follow-up explanations. Stored action plans still capture approved paths and proposed new-file content after recognized-secret redaction.

Model-file verification and the preserved launch/reveal adapters now use workers as well. General file changes have a separate schema-v1 journal with per-step state, exclusive destinations, source/root identity revalidation, cancellation and a time limit. They have no automatic undo/recovery UI. The existing photo journal and undo are unchanged; no user/model/history database migration or filesystem operation occurs at startup beyond app-owned state.

UI screens show actual tool cards and supported suggestions, keep the composer enabled for status/cancel while busy, and prioritize the approval preview. Dashboard summaries update from completed tools; metrics are timestamped snapshots. Complete themes, native installers, elevated automation, general autonomous planning and advanced deferred tasks remain out of scope.
