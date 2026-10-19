# M1 verification — 2026-10-18

Scope: installed repository guidance, M0 audit, architecture/app shell and the M1 SQLite conversation slice. The entire LocalMind product is not declared complete.

## Results

- `LOCALMIND_CAPTURE_DIR=artifacts .venv/bin/pytest -q`: **50 passed, 19 subtests passed in 8.71 seconds**.
- `.venv/bin/ruff check .`: passed.
- `.venv/bin/python -m compileall -q src tests`: passed.
- `.venv/bin/python -m pip check`: no broken requirements.
- QML lint passed with `--unqualified disable --missing-property disable`; runtime GUI tests captured no TypeError, ReferenceError, binding loops or native-style customization errors.
- Domain dependency inspection passed.
- Supplied root instruction/prompt files exactly match their Downloads originals. The master guide is a documented local consolidation, not a claimed copy of a missing original.

## Covered scenarios

Migration from a new database; future/unversioned/corrupt database refusal without reset; foreign keys and rollback; message ordering across tied timestamps; selected-conversation restart; credential-pattern redaction; SQL-like text as data; structured context bounds; plan/approval/execution linkage; retention and cascading clear; independent undo preservation; SQLite writes off the GUI thread; queued old-conversation writes during switching; no restored live photo approval; denied clear/retention dialogs; navigation, input, progress/cancel, actual approved file moves and undo.

Existing real local-model tests block network connections. The 1,200-image regression uses temporary files. No user photos or user history databases were modified by verification.

## Screenshots

Offscreen software rendering with actual view models and isolated test fixtures:

| View | 1440×900 | 1280×800 | 900×700 |
| --- | --- | --- | --- |
| Assistant | [Preview](assistant-1440x900.png) | [Preview](assistant-1280x800.png) | [Preview](assistant-900x700.png) |
| History | [Preview](m1-history-1440x900.png) | [Preview](m1-history-1280x800.png) | [Preview](m1-history-900x700.png) |
| Settings | [Preview](m1-settings-1440x900.png) | [Preview](m1-settings-1280x800.png) | [Preview](m1-settings-900x700.png) |

macOS ARM64 only. Native platform rendering, Windows/Linux behavior and installers are not verified. No type-checker is configured. Later milestone gaps remain recorded in docs/IMPLEMENTATION_STATUS.md.
