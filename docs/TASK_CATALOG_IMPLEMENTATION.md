# Installed task catalog

The pasted specification is preserved in [SUPPORTED_TASK_CATALOG.md](SUPPORTED_TASK_CATALOG.md). This is the implementation matrix, not a claim that every proposed task exists.

48 catalog task IDs share six service handlers. Several IDs are views/aliases over the same inspected facts, rather than separate AI models or isolated prompt commands. `docs/task-registry.json` exports their actual contracts. Conversational follow-ups are implemented in the Assistant state machine; they do not add executable capabilities.

| Service | Installed IDs | Limits and evidence |
| --- | --- | --- |
| folder | F01, F02, F03, F04, F05, F06, F07, F11, F13, F14, F15, C15 | Metadata only; counts, logical size, extension totals, top files, recent modifications, empty directories, subfolder bytes, exclusions and filename/extension matching. 100k entries/depth24/15s; partial results explicit. |
| project | P01, P02, P03, P04, P05, P06, P07, P15 | Python/Node manifest parsing, source-extension language evidence, framework/dependency declarations, top-level structure, README excerpt and entry-point candidates. No project execution. Dart/Rust manifests detected, not dependency-parsed. |
| preview | C01, C02, C03, C04, C09, C10, C13, C14 | Bounded UTF-8 text/source/Markdown, JSON, CSV, word/line counts, headings and metadata. 256KB reads/6k-character excerpts. Binary formats and other encodings fail gracefully; no PDF/DOCX extraction. |
| files | FM01, FM02, FM03, FM04, FM05, FM13, FM15 | Create directory/text, rename/move/copy one regular file, batch organization by extension. All return immutable previews before commit. Relative paths in one root, no overwrites. 5k changes, 30s preview, 2GiB per copy, 2min commit limit; no generic automatic undo. |
| desktop | A01, A02, A03, A04 | Known app allowlist, safe existing local documents, current/named folder and validated HTTP(S) websites. OS handoff on workers, no shell. Native Windows/Linux not verified here. |
| system | S01, S02, S03, S04, S05, S06, S08, S11, S12 | Timestamped psutil CPU, RAM, disk, OS, uptime and supported battery/top-memory process readings. Snapshots, not continuous monitoring. Missing platform readings are reported. |

## Preserved photo workflow

Photo month/year/format grouping remains the existing EXIF-aware planner, explicit approval, durable per-file journal and undo. This also covers catalog FM06. It has its own larger preview limits and independent journal; clearing chat does not erase it.

## Conversation behavior

Greeting/help, actual-result explanations, folder/file references, exact pending-plan chat approval, cancellation/status during tasks, live recent activity/error explanation, supported suggestions, conversation reset and actual last-scan counts are implemented. File ambiguity asks for a quoted relative filename. Live result references and approval are intentionally cleared on history restore. Declining/cancelling a preview cannot move files.

## Multi-step boundary

The target Downloads workflow runs overview → largest files → PDF-only preview. Tools run sequentially, with at most six steps and a hard stop at approval. No later action auto-resumes after approval. Combinations the parser cannot represent ask for separate requests; unsupported destructive/elevated steps are rejected. This is bounded semantic intent retrieval plus deterministic services, not a generative autonomous planner.

## Deferred proposed tasks

Duplicate hashing/review; old-file age filters and folder comparisons; batch rename; ZIP creation/extraction; trash/restore; text replacement; Git status/commits; TODO scanning; arbitrary function explanation; unused dependencies; full PDF/DOCX extraction; cross-file content search/comparison/log explanations; application closing/settings/terminal control; CPU process ranking/network/partition enumeration; scheduling and vision grouping remain unavailable. Cross-workspace move/copy is also deferred. Do not suggest these actions from the UI.

## Approval and recovery

Photo undo is automatic and durable. General file operations have **no automatic undo or crash-recovery UI**. A separate versioned SQLite journal records the immutable plan, started steps, successful steps, failures and terminal state. Interrupted source/destination paths require manual review; no unfinished write is replayed at startup. Static path/symlink/root/file identity checks and exclusive writes protect normal use, not a hostile process racing directory replacement.

## Platform and privacy

Verified on macOS ARM64 using offscreen Qt. Real external app/browser launches are mocked in tests. Windows/Linux adapters require native runners. Explicit website opening delegates network access to the browser; LocalMind itself sends no chat/file data online. Model downloads remain explicit and pinned; no new model was downloaded for this expansion. Extracted file/project bodies and their follow-up explanations remain live-only and are omitted from persistent chat/event summaries. History remains a redacted local plaintext store.
