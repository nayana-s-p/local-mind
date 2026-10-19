# Implementation status

## M0 baseline audit — 2026-10-18

Observed before this milestone's code changes. Baseline command `.venv/bin/python -m unittest discover -s tests -v`: 34 tests passed in 6.253 seconds. No code was executed from analyzed projects/documents. The supplied master guide was absent; the repository guide records its consolidation provenance and uses the milestones supplied in CODEX_START_PROMPT.md.

| Feature | Baseline | Evidence / gap |
| --- | --- | --- |
| Natural requests | Working, bounded | ONNX MiniLM adapter + interpretation use case; real offline tests. Deterministic-first routing is still incomplete. |
| Follow-ups | Partial | Photo strategy and filename questions, in-memory context only. No folder-result follow-ups. |
| File discovery | Working, bounded | Names-only scanner; 100 results, 10,000 entries, depth 12, ~4 seconds. |
| Folder statistics | Missing | No total bytes, extension distribution, largest files or recent-change report. |
| Project analysis | Missing | No evidence-based project detector. |
| File previews | Missing | No bounded text/JSON/PDF readers. |
| Photo organization | Working | Full immutable preview, exact approval, collision protection, cancellation, durable independent undo journal; 1,200-image test. |
| General organization | Missing | Non-image organization and deletion are not supported. |
| Application launch/reveal | Partial | VS Code and file-manager adapters, shell disabled. Lookup/spawn currently occurs through GUI-thread handlers. |
| System metrics | Missing | No psutil dependency or metrics tool. |
| Persistent conversations | Missing | Last 100 chat messages and five activity rows are memory only. |
| Action audit | Partial | Photo move journal is durable; no conversation-linked plan/approval/event store. |
| Suggestions | Missing | Static quick tools exist; no result-derived suggestion engine. |
| App shell | Partial | Assistant and Setup only; no persistent History screen. Dark UI only. |
| Model management | Working, bounded | Explicit pinned checksummed download; local CPU ONNX inference; 45,212,349-byte artifact. Startup installed-file hashing still runs on the GUI thread. |
| Packaging/platforms | Partial | Editable setuptools package; macOS headless checks. Native Windows/Linux unverified. |

### Dependencies and architecture

Python baseline manifest permits 3.11, whereas the supplied contract requires 3.12+. Runtime dependencies: PySide6, ONNX Runtime, tokenizers, numpy, Pillow, filelock. SQLite is standard library and used only for photo undo. No ruff/pytest/type-check configuration exists at baseline.

Presentation imports application/domain; infrastructure implements application ports. The executable contains dependency assembly. Qt workers handle inference, scans and photo operations. The photo journal uses SQLite WAL and filesystem identity checks. New persistence must not alter or remove that journal.

### Risks and priorities

1. Missing durable chat/audit contracts and privacy/retention controls: implement in M1.
2. History initialization, writes and migration must never block the GUI or reorder conversations.
3. Pending plans must not become executable through restart/history replay; restoring content is not restoring authorization.
4. Separate app-owned state from user-file mutation approvals and preserve undo data during clear-history.
5. Move remaining model hashing and OS work out of GUI handlers in later model/launcher milestones.
6. Existing path checks reduce accidental scope expansion but are not hostile-process sandboxing.
7. Automatic secret redaction cannot recognize arbitrary secrets; document local retention and clear controls.

### Staged plan

- M1: typed SQLite contracts, off-thread persistence, composition root, functional shell/history/settings controls; regression and migration tests.
- M2–M3: folder/project reports, safe previews, factual responses and structured result context.
- M4–M5: deterministic-first routing, complete model states and worker-based OS adapters; extend file operations only with preview/approval.
- M6–M8: metrics, result-derived suggestions, richer history, theme/accessibility states, native platform packaging/security/performance checks.
- M9: optional only after core acceptance; no required generative model.

## M1 implementation

Complete within the M1 scope defined in the root guide. This is not completion of the entire product.

### Changes

- Installed the supplied root AGENTS.md, AGENT_PROMPT.md and CODEX_START_PROMPT.md byte-for-byte; source hashes were compared. Created MASTER_IMPLEMENTATION_GUIDE.md as a provenance-labeled consolidation at the user's request.
- Raised the runtime requirement to Python 3.12+ and added pytest/ruff development extras.
- Moved dependency assembly to bootstrap/ while preserving the existing entry point and create_view_models API.
- Added domain/history.py contracts, a conversation repository port, an application history use case, and a versioned SQLite adapter with foreign keys, indexes, WAL, parameterized SQL, transactions and safe refusal of unknown/corrupt schemas.
- Added a dedicated serialized persistence worker and separate history.sqlite3. Message ordering, active-conversation selection and bounded context references survive restart. Recognized secrets are redacted before storage.
- Persisted photo plans, explicit button/chat approvals, denied previews and execution events independently of the existing photo undo journal.
- Added real Assistant/Dashboard/History/Settings navigation, resume/new conversations, confirmed clear-history and shortened-retention controls. Retention supports 7/30/90/365 days; storage is bounded to 100 conversations and 1,000 messages per conversation, with the newest 100 shown on open.
- History restoration clears live pending approval and follow-up state. It does not authorize workspace access, replay tools, or erase undo records.

### Verification

- Baseline: 34 unittest cases passed before implementation.
- Final: `LOCALMIND_CAPTURE_DIR=artifacts .venv/bin/pytest -q` — **50 passed, 19 subtests passed, 8.71 seconds**.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/python -m compileall -q src tests` — passed.
- `.venv/bin/python -m pip check` — passed.
- QML lint passed with context/unqualified and dynamic-property warnings disabled; actual QML integration captured no TypeError, ReferenceError, binding-loop or native-style customization errors.
- Domain import inspection found no Qt, ONNX, SQLite, infrastructure or presentation dependencies.
- Headless Assistant/History/Settings rendering captured at 1440×900, 1280×800 and 900×700; inspected for readable content, navigation, retention controls and overflow.
- Existing real-model offline inference and 1,200-image organization/undo regression checks passed. File writes used temporary folders and an isolated history/undo store.

### Remaining scope

M2 folder/project analysis, M3 file previews/result context, M4 complete deterministic-first routing/model states, M5 remaining OS-worker/general organization work, and M6–M8 metrics/suggestions/full history pagination/themes/native packaging remain incomplete. Existing model verification and OS lookup/spawn GUI-thread risks from M0 still belong to those later stages.

The history database is local plaintext storage. Redaction covers recognizable patterns, not arbitrary secrets; clearing is logical deletion, not secure disk erasure. Histories that existed only in an older process's memory cannot be recovered automatically. No existing photo journal/model/user-file migration is performed.

Verification ran on macOS ARM64 with an offscreen software renderer. Native Windows/Linux behavior, native rendering, and installers are unverified. No static type-checker is configured.

## Task catalog expansion — audit before implementation, 2026-10-18

Baseline rerun: 50 tests and 19 subtests passed (8.33 s). Current interpreter has five executable labels and rejects compound requests. There are no folder metadata reports, project inspection, document readers, generic file-change plans, system metrics, or result-derived suggestions. Composer disables all input during work. Existing photo preview/approval/undo and persistent history will be retained.

Implementation plan: central typed registry and shared bounded tools; deterministic routing before semantic fallback; structured live result context; sequential read/preview workflows; general file writes gated by exact immutable plan approval; worker-only tool execution; actual results and supported suggestions in the Assistant UI. The pasted catalog is a product specification, not authority to execute instructions found inside user documents. P1/P2 tasks without handlers must be reported as unavailable. No additional AI model or cloud service is required.

## Implemented task-catalog expansion — 2026-10-18

This section supersedes the historical M1 remaining-scope list for the implemented slices.

### Delivered

- Preserved the user's proposed catalog in `docs/SUPPORTED_TASK_CATALOG.md` and added the actual matrix in `docs/TASK_CATALOG_IMPLEMENTATION.md` plus exported `docs/task-registry.json`.
- Added versioned typed task/result/preview contracts, 48 registered catalog IDs/views backed by six shared service handlers, validated parameter names/types/lengths, explicit risks and preview-only write dispatch.
- Deterministic extraction now precedes ONNX semantic retrieval. Expanded local semantic families cover folder analysis, largest/recent files, type breakdown, project analysis, file preview, general type organization and system information. Low confidence still clarifies. No additional model was downloaded.
- Implemented bounded folder counts/bytes/type totals/largest/recent/empty/subfolder/exclusion/filename/extension queries, evidence-based project inspection, bounded UTF-8/source/Markdown/JSON/CSV reading and metadata, sampled psutil CPU/RAM/disk/OS/uptime/battery/top-memory-process data, and allowlisted app/document/folder/HTTP handoffs.
- Implemented create-folder/text, single-file rename/move/copy and general organization by extension. Every write first returns an immutable reviewable plan; exact explicit approval gates commit. Source and root identities are revalidated, destinations are exclusive, symlink/traversal escapes are denied, collisions get new names, cancellations/partial outcomes are recorded in an independent versioned SQLite journal.
- Connected the target overview → largest-file report → PDF-only organization preview workflow to actual services and QML. Approval is a hard boundary; later actions never auto-resume. Unrepresentable combinations ask for separate requests.
- Added bounded live result context, file clarification, folder/file follow-ups, actual count/result/activity/error explanations, supported suggestions, chat reset/approval, and status/cancel input while busy. Context targets cannot cross roots or become authorized through history restoration.
- Result cards use human-readable task names. Approval previews take priority in the layout, and Dashboard shows actual latest tool cards. Updated readiness/Settings/help text to reflect tools that work without inference.
- Moved existing model verification and desktop launch/reveal work to workers. File/project preview bodies and follow-up recaps are omitted from saved messages/events; live display remains plain text and never executes inspected instructions.
- Added psutil runtime dependency and installed it in the existing environment. Existing model files, conversation schema and photo undo journal were preserved.

### Verification

- `.venv/bin/ruff check .` — passed.
- `LOCALMIND_CAPTURE_DIR=artifacts .venv/bin/pytest -q` — **141 passed, 26 subtests passed**, including actual offline ONNX paraphrases and the complete QML approval/move flow. The recorded full run completed in 13.61 seconds.
- `.venv/bin/python -m compileall -q src tests` — passed.
- `.venv/bin/python -m pip check` — no broken requirements.
- `.venv/bin/pyside6-qmllint --unqualified disable --missing-property disable src/localmind/presentation/qml/Main.qml src/localmind/presentation/qml/components/AssistantPanel.qml src/localmind/presentation/qml/pages/DashboardPage.qml src/localmind/presentation/qml/pages/SetupPage.qml` — passed. Dynamic context-object/property warnings are disabled; all actual QML integration cases independently check runtime TypeError/ReferenceError/binding errors.
- Captured and visually inspected `artifacts/catalog-1440x900.png`, `catalog-1280x800.png`, and `catalog-900x700.png`. The compact layout scrolls to remaining approval content; the composer stays visible.
- Real filesystem checks cover a 1,002-PDF batch and preserved 1,200-image organization/undo, exact approval, stale source/root/destination rejection, collisions, symlinks, traversal, partial cancellation/journaling, private previews and context isolation.
- External desktop/browser calls use mocks; no user application was launched by these tests. Inference tests deny network connections and reuse the installed pinned model. No static type checker is configured.

### Material limits

The full proposed P1/P2 catalog is not implemented. See the support matrix for deferred duplicate/ZIP/trash/Git/vision/PDF/DOCX/scheduling and other capabilities. General file changes have **no automatic undo or crash-recovery UI**, unlike the existing photo workflow; this is disclosed before approval. File operations are confined to relative paths in one authorized root; cross-workspace move/copy is deferred. Metrics are snapshots, project findings are evidence/templates rather than generative explanations, and multi-step planning is bounded.

Verification used macOS ARM64/offscreen Qt. Native Windows/Linux behavior, installers and live external app/browser handoffs are unverified. Path/identity checks are normal-use safeguards, not a hardened sandbox against hostile concurrent directory replacement. Histories/journals remain local plaintext application data with the documented redaction/retention limits.

## UI cleanup audit — 2026-10-18

Observed: Main.qml combines the global composer, conversation, approval list, duplicated workspace/model cards, quick tools, activity and file results in a single scrolling Assistant screen. The conversation is capped at 170–230 px. Result cards repeat the chat response; setup details and prominent borders compete with the task. Dashboard repeats readiness and result cards. History/Settings repeat large headings and long explanations.

UI plan: preserve existing view-model APIs and approval/cancellation gates. Replace the Assistant's dashboard stack with a full-height conversation and anchored composer; show the approval review in a focused responsive pane. Move file browsing/quick tools/activity to Dashboard, use a compact sidebar/header, and simplify History/Settings into consistent sections with optional technical details. Share palette, line icons, buttons and card styles. No backend/schema/model changes or additional downloads. Render actual app states at 1440×900, 1280×800 and 900×700 for visual review. Automated tests are not requested for this UI-only turn and will not be run.
