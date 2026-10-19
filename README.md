# LocalMind

LocalMind is a Python/PySide6 desktop assistant that understands English requests locally and executes supported actions through deterministic tools. The ONNX model is connected to interpretation; requests do not need to match fixed phrases. Current tools cover folder statistics and queries, evidence-based project inspection, bounded file previews, approved file operations, photo organization, known desktop targets, and local system metrics. A typed registry connects requests to real handlers.

## Run

Python 3.12 or newer is required. From this folder on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m localmind
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m localmind
```

For an existing installation, close the app, activate its environment, run `python -m pip install -e .` to add the runtime dependencies (including psutil), then restart. An already running process does not reload Python changes.

Choose a workspace, or explicitly name a supported user folder such as Downloads. Deterministic tools work immediately. In **Settings**, download the local language model if missing for additional semantic matching. Downloads start only when you press the button. Existing verified files are reused. Type into **Tell LocalMind what to do** and press Return or Send. Cmd+K on macOS / Ctrl+K elsewhere focuses the input.

## Organize thousands of photos

1. Select the folder containing your photos using **Choose workspace**.
2. Ask: “There are thousands of photos here. Can you help me get them organized?”
3. Answer the follow-up with “by month,” “by year,” or “by file format.” You can specify grouping in the first request too.
4. Review the complete, scrollable source/destination list. Say “by year instead” to change grouping, or discard the preview.
5. Click **Approve … changes** or reply “yes, do it” to approve that exact plan.
6. **Undo last photo organization** restores original paths, including after restarting and selecting the same workspace again.

Month grouping produces `Organized Photos/YYYY/MM/original-name.jpg`. Year grouping uses `Organized Photos/YYYY/`; format grouping uses folders such as `JPEG/` and `PNG/`. JPG/JPEG share a folder. Date grouping prefers EXIF date taken, then uses file modification dates with the fallback count shown. HEIC/HEIF/DNG files may require this fallback when metadata cannot be read. Grouping by people, scenes, or objects is not available.

Planning supports 50,000 images, 150,000 entries, depth 32, and two minutes. A limit fails the preview without moving anything. It is independent of the smaller discovery result cap. Existing `Organized Photos` output is excluded. Non-image files remain in place. Symlinks, inaccessible entries, and other mounted filesystems are skipped and counted.

Names are preserved except for collision suffixes such as `photo (2).jpg`. Each source must still match its preview identity, size, and modification time. Moves create an exclusive hard link then remove the old link, so an existing destination cannot be replaced. The workspace disk must support hard links. Unsupported disks fail visibly. Stop requests take effect between files; completed moves remain recorded.

Undo pauses on edited/replaced images or occupied original filenames, leaving them untouched. A SQLite write-ahead journal supports recovery from interruption between link creation and source removal. Retain LocalMind's application data directory to preserve undo history.

## Ordinary requests and follow-ups

Type your request in the composer; no slash-command syntax is required. For example:

> Check my Downloads folder, give me a quick summary, show the biggest files, and help me organize the PDFs.

This runs a bounded metadata analysis and largest-file report, then prepares a PDF-only organization preview. Nothing moves until you click **Approve … changes** or say **Yes, organize those files**. Other combinations that cannot be represented reliably ask for separate requests. Approval ends the workflow; later actions never auto-resume.

| Ask naturally | Actual behavior |
| --- | --- |
| “How many files are here, and how much space do they use?” | Metadata counts and logical bytes, with exclusions/partial status. |
| “Which type is largest?” / “Show the largest file in it.” | Uses the live folder context; extension sizes or top-ten files. |
| “What changed this week?” | Local calendar week, file modification time; download dates are not inferred. |
| “Explain this project.” / “What libraries does it use?” | Source extensions, manifests, dependency declarations, framework evidence, structure and entry-point candidates. Does not run the project. |
| “Read notes.md.” / “Inspect settings.json.” | Bounded UTF-8 preview, word/line facts, JSON validation/keys. CSV columns and Markdown headings are supported. |
| “Create a folder named Reports.” | Preview, approval, exclusive creation. |
| “Create a text file named notes.txt containing hello.” | Shows the exact new text before approval. A new README starts with the folder-name heading. |
| “Rename notes.txt to notes.md.” / “Copy notes.md to archive/notes.md.” | One regular file, relative paths inside the authorized workspace, preview and approval. |
| “Separate images, PDFs, and videos.” | Preview moves into `Organized Files/EXTENSION/`; collision suffixes preserve existing files. |
| “Open that folder.” / “Open this file.” | Uses live scope/file references. Ambiguous files ask for a relative filename. Scripts/executables cannot be opened through the document tool. |
| “Open VS Code.” / “Open Safari.” / “Open GitHub.” | Allowlisted installed application or validated HTTP website, through an OS adapter without a shell. Launch handoff is reported; app readiness is not monitored. |
| “Tell me about my computer.” / “What's using the most RAM?” | Timestamped psutil CPU/RAM/disk/OS snapshot and available top-memory process readings. |
| “What does that mean?” / “What should I do next?” | Verified result recap and supported suggestions. Suggestions require a click or request. |
| “Has the scan finished?” / “Cancel that operation.” | Works while a task is running; cancellation is acknowledged by the worker. |

File discovery quick tools retain their small 100-result, 10,000-entry, depth-12, ~4-second scan. Folder reports use metadata only: 100,000 entries, depth 24, 15 seconds, at most 100 displayed file rows. Hidden entries, dependency folders, links and other volumes are excluded and counted. Empty-folder checks inspect actual directory entries. Partial reports never claim whole-folder totals.

Project inspection checks at most 30,000 entries/10 seconds and reads each manifest up to 256 KB; README excerpts are bounded. Python and Node dependency/script declarations are parsed. Dart/Rust manifests are detected but their dependencies are not parsed. File previews read at most 256 KB and display at most 6,000 characters; word/line counts describe the preview when truncated. Only UTF-8 text is decoded. PDF/DOCX extraction is not installed; safe desktop opening and metadata remain available.

Named scopes are Downloads, Documents, Pictures, Desktop, Movies and Music beneath the user's home. Other folders must be selected as the workspace. An explicit subfolder path must remain inside an authorized scope. File mutations support relative destinations within one root; cross-workspace moves/copies ask for a relative destination instead of guessing. Network-mounted roots can cause OS filesystem traffic.

General organization previews are limited to 5,000 changes. Copies are limited to 2 GiB/file and batches to two minutes. All sources and the root identity are checked again before commit; destinations are never overwritten. A separate SQLite journal records started/completed/failed steps and exact partial counts. General file operations **have no automatic undo or crash-recovery UI**; the existing photo workflow retains its durable undo. Review the preview and this distinction before approving.

## Understanding and limits

The pinned [all-MiniLM-L6-v2 model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) runs through ONNX Runtime on CPU. Local tokenization, masked mean pooling, and normalization produce embeddings. Similarity to capability examples selects intent by meaning. Low similarity, a close alternative, or an unsupported intent prompts clarification. Scores are not probabilities. Typed argument checks, workspace policy, and approval independently constrain execution. The model never supplies shell commands.

The ONNX artifact is 45,212,349 bytes, below the 200 MB artifact target; total download is 45,678,786 bytes. SHA-256 and sizes are checked against pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` before installation and first inference. Setup retains explicit download consent and atomic installation. Inference reads local files only, has no cloud fallback, and disables ONNX telemetry. Deterministic extraction runs first, then the local semantic model handles additional paraphrases. Missing models never trigger a cloud fallback or download; ambiguous requests ask for clarification.

This is semantic intent retrieval, not an open-ended conversational LLM. Natural phrasing works within supported capabilities; new tasks need real tools. Open-ended conversation, arbitrary desktop control, visual/semantic photo grouping, generative content understanding, deletion/trash, duplicate detection, ZIP operations, scheduling, arbitrary shell execution and unrestricted multi-task planning remain unavailable. The installed task matrix and deferred catalog entries are documented in `docs/TASK_CATALOG_IMPLEMENTATION.md`. The photo workflow is interpretation → clarification → scan → preview → approval → moves → optional undo.

## Architecture and storage

- `presentation/assistant_viewmodel.py`: conversation, follow-ups, approval, workers, cancellation, and lazy full-plan model.
- `application/catalog_router.py`, `application/task_registry.py`, `application/use_cases/run_tasks.py`: deterministic slot extraction, validated task dispatch, bounded sequential tools and live references.
- `infrastructure/filesystem/inspection.py`, `file_actions.py`: factual inspection and approved general file changes.
- `infrastructure/platform/catalog_desktop.py`, `system_metrics.py`: allowlisted desktop handoffs and sampled local metrics.
- `application/use_cases/interpret_request.py`: deterministic/semantic decisions and clarification.
- `infrastructure/models/intent_classifier.py`: verified ONNX loading, local tokenizer, pooling, and retrieval.
- `application/use_cases/organize_photos.py`: grouping validation and exact-plan authorization.
- `infrastructure/filesystem/photo_organizer.py`: metadata, scoped planning, exclusive moves, interprocess workspace locks, durable journal, and undo.
- `bootstrap/`: dependency composition and Qt signal wiring; `__main__.py` owns startup/lifecycle. QML handles presentation.
- `infrastructure/persistence/history.py`: versioned conversation, context, plan, approval, event, and retention storage.
- `presentation/history_viewmodel.py`: serialized background persistence and history controls.

Inference, inspection, moves, undo, scans, downloads, model verification and OS handoffs use workers. Shutdown cancels and waits for workers. The journal stores IDs, workspace/relative paths, file identities, and move states; no image contents or raw prompts. Conversations are now persisted in a separate local `history.sqlite3`; the newest 100 messages are loaded when a conversation is opened. The dashboard activity strip remains session-only. Storage follows Windows LocalAppData, macOS Application Support, and Linux XDG conventions.

Canonicalization, symlink checks, snapshot validation, exclusive destinations, and locking reduce accidental scope expansion. They are not a hardened sandbox against a hostile process continuously changing the directory tree. Use folders you control.

## Conversation history and repository guidance

The sidebar now provides Assistant, Dashboard, History, and Settings. History resumes the last selected conversation, supports new conversations and reopening saved messages, and requires confirmation before clearing history or shortening retention. Settings offers 7/30/90/365-day retention. Storage keeps at most 100 conversations and 1,000 messages per conversation, with the latest 100 loaded into the chat view. The separate photo undo journal is preserved when chat is cleared. Clearing records is a logical deletion, not a secure disk-erasure guarantee.

Recognized API keys, credential assignments, bearer tokens, and private-key blocks are redacted before persistence. Automatic redaction cannot recognize arbitrary secrets; avoid entering them. History is plaintext application data, not an encrypted secret store. Context contains bounded workspace/tool/plan references. Extracted file/project bodies are displayed only in the live session and omitted from persisted messages/events; saved records indicate that content inspection occurred. Follow-up result explanations also avoid persisting extracted bodies. Structured file targets and live approval state are cleared on conversation restore. Restoring history never selects a workspace as authorization, replays tools, or restores a pending approval. Chats from an older running version that existed only in memory cannot be recovered automatically.

The root `AGENTS.md`, `AGENT_PROMPT.md`, and `CODEX_START_PROMPT.md` are the supplied repository guidance. `MASTER_IMPLEMENTATION_GUIDE.md` was created here as a documented consolidation because no original master file was found. `docs/IMPLEMENTATION_STATUS.md` records the M0 audit and current milestone; M1 established the shell and SQLite slice; the task-catalog expansion adds folder/project/file/system tools, contextual follow-ups and general approval previews. The status document distinguishes implemented handlers from deferred advanced tasks.

## Verification

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

Tests use temporary folders and an isolated journal. Coverage includes a 1,200-image batch, EXIF/fallbacks, collisions, stale previews, scope escapes, cancellation, interruption recovery, edited-file preservation, and QML integration. Real-model tests disable network connections; they skip if the explicitly provisioned model is missing, without downloading it.

Capture headless desktop previews:

```bash
LOCALMIND_CAPTURE_DIR=artifacts python -m unittest discover -s tests -p 'test_desktop_integration.py' -v
```

Screenshots use Qt's offscreen software renderer at 1440×900, 1280×800, and 900×700. Native Windows/Linux behavior still needs platform runners.
