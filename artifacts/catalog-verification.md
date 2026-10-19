# Task catalog verification

Environment: macOS ARM64, Python 3.14, PySide6 6.12, offscreen software Qt. No new model download; installed pinned MiniLM reused. Application/database/filesystem checks use temporary roots and isolated stores.

- `LOCALMIND_CAPTURE_DIR=artifacts .venv/bin/pytest -q`: 141 passed, 26 subtests passed (13.61 seconds in the recorded run).
- `.venv/bin/ruff check .`: passed.
- `.venv/bin/python -m compileall -q src tests`: passed.
- `.venv/bin/python -m pip check`: no broken requirements.
- QML lint: passed with `--unqualified disable --missing-property disable`; runtime GUI tests additionally reject TypeError, ReferenceError, binding-loop and native-control customization errors.

New coverage: catalog slot extraction, semantic offline paraphrases, actual folder/project/text/JSON/CSV/system results, the target summary/largest/PDF workflow, exact approval, filesystem/root/destination revalidation, collision handling, explicit scope changes, link/traversal denial, executable/URL denial, cancelled planning/partial commits, 1,002 PDF changes, no content retention, status/cancel while busy, off-thread verification/reveal, and no approval replay. Existing history/model/1,200-photo regression cases pass.

Visually inspected:

- [1440×900](catalog-1440x900.png)
- [1280×800](catalog-1280x800.png)
- [900×700](catalog-900x700.png)

Desktop/browser opens are mocked; no actual launch validation or native Windows/Linux run is claimed. General file changes are journaled but have no automatic undo/recovery UI. See [the support matrix](../docs/TASK_CATALOG_IMPLEMENTATION.md) for implemented and deferred tasks.
