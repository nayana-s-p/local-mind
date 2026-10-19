# Assistant implementation decision

The previous router matched a short regex grammar. Setup downloaded MiniLM without connecting it to inference. No photo-writing tool existed. This change implements a bounded semantic assistant with real photo organization.

## Data flow and trust boundaries

`QML → DashboardViewModel.assistantRequest → AssistantViewModel worker → InterpretAssistantRequest → IntentClassifier port → verified local ONNX adapter → typed decision`.

Five action capabilities are allowlisted: organize photos, list files, search filenames, find PDFs, and launch VS Code. Low similarity or a close alternative prompts clarification. Independent checks reject unsupported modifications and visual grouping. Natural phrasing grants no additional permissions.

Photos without grouping enter `awaiting_strategy`. A grouping enters `planning`; the resulting immutable plan enters `awaiting_approval`. A lazy QML model exposes every move. Changing grouping invalidates the plan. Applying requires its exact ID and validates all source snapshots before any move.

`approved plan → OrganizePhotos → PhotoOrganizer port → filesystem adapter → durable intent → exclusive destination link → source unlink → durable completion`.

SQLite stores operation states `applying/completed/partial/undoing/undone` and move states `pending/moving/moved/undoing/undone`. Cancellation stops between files, retaining completed moves for undo. A crash leaving `applying` blocks new organization until undo resolves it. Undo reconciles interruption between link and unlink. Per-workspace OS-backed locks serialize mutation and release on process termination.

## Decisions and failures

- Reuse the explicitly provisioned MiniLM package: meaning-based retrieval within a bounded tool set, CPU inference, under-200 MB artifact, no additional model download.
- Keep execution deterministic. Embeddings do not provide general reasoning, unrestricted argument generation, or vision.
- Preview creates no output directories; limits fail the whole preview.
- Stay within the selected canonical workspace/filesystem. Exclude symlinks and other mounts.
- Allocate existing/planned destination names case-insensitively. Exclusive link creation prevents replacement.
- Commit move intent before filesystem mutation; partial results remain recoverable.
- Pause undo on missing, changed, or conflicting images. Remove only known empty directories created by this operation.
- Keep prompt/image contents off the network and out of durable audit records.
- Path checks are not handle-based confinement against malicious directory substitution.

## Compatibility and migration

Existing discovery, reveal, explicit setup, and confirmed VS Code launch remain. Exact legacy commands retain a basic-tools fallback without inference. File delegates explicitly declare model roles. Qt Quick Controls uses Basic to support custom controls.

The journal is new SQLite schema version 1 outside the workspace; newer versions are refused. Existing models are reused. Install new Python dependencies through the normal editable install. Upgrading performs no image migration.

## Acceptance

Tests cover actual temporary file operations, journal reopening, 1,200-image organization/undo, interrupted link/unlink recovery, interpretation policy, and real offline inference. Desktop checks load the actual QML, submit through its field, verify follow-ups and previews, activate approval, move images, and undo them. Three offscreen screenshot sizes cover layout; native Windows/Linux checks remain.
