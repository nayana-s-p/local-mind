# Codex Start Prompt — LocalMind

You are implementing LocalMind in this existing repository. Read `AGENTS.md` in full and treat it as the project's engineering contract.

## Product objective
Create a polished, reliable, offline-first Python desktop assistant that accepts conversational commands and performs small useful tasks: folder overview, project overview, file previews, safe file organization, app launching, system information, persistent chat history, and context-aware suggestions. Keep the ONNX intent model under 200 MB; do not introduce a mandatory generative LLM or complex autonomous agent framework.

## Immediate task: repository audit first
1. Inspect existing code, tests, dependencies, build scripts, database, ONNX assets, QML screens, and documentation.
2. Classify each required feature as working / partial / missing / broken, with file references and evidence.
3. Identify security, concurrency, architecture, and cross-platform issues.
4. Create/update `docs/IMPLEMENTATION_STATUS.md` and `docs/ARCHITECTURE.md` with the observed system and a staged migration plan.
5. Only then implement the first smallest independently testable milestone. Do not delete or rewrite existing working features without justification.

## Milestones
M0 audit; M1 architecture + app shell + SQLite; M2 folder/project analysis; M3 preview + short factual responses + follow-up context; M4 ONNX routing/model manager; M5 safe organization + application launcher; M6 system info/history/suggestions; M7 complete QML dashboard and chat UX; M8 test hardening, security, packaging; M9 optional small generative model (separate opt-in).

## Definition of done
For each milestone: real implementation, typed contracts, failure/cancellation states, tests, no fabricated outputs, docs updated, and a report of what was verified versus what remains unverified. Use actual runtime checks when possible.

Start M0 now. If the repository is empty, scaffold M1 after documenting that finding. Continue incrementally within the available execution time; prioritize working vertical slices over broad incomplete scaffolding.
