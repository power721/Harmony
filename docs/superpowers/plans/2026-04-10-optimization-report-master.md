# Optimization Report Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the valid items from `docs/optimization-report-2026-04-10.md` with one report item per commit, while documenting skipped items and preserving unrelated local changes.

**Architecture:** The report spans multiple independent subsystems, so execution is split into four wave plans instead of one oversized branch of work. Each wave plan owns a coherent slice of the codebase, but commit boundaries still follow the report item numbers, not the wave boundaries.

**Tech Stack:** Python 3.11+, PySide6, SQLite, pytest, uv, git

---

## File Map

- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-a-repositories-db.md`
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-b-audio-runtime.md`
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-c-system-services.md`
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-d-ui-utils-domain.md`
- Reference: `docs/optimization-report-2026-04-10.md`
- Reference: `docs/superpowers/specs/2026-04-10-optimization-report-execution-design.md`

### Task 1: Prepare The Execution Baseline

**Files:**
- Modify: `docs/optimization-report-2026-04-10.md`
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-master.md`

- [ ] **Step 1: Capture the report item list and execution notes**

```bash
rg -n "^### " docs/optimization-report-2026-04-10.md
git status --short
```

- [ ] **Step 2: Confirm that unrelated files stay out of scope**

Run: `git status --short`
Expected: local changes such as `.python-version` remain unstaged throughout execution.

- [ ] **Step 3: Use the wave plans as the only execution order**

```text
Wave A: repositories, database, repository-side validation
Wave B: audio engine, mpv, HTTP, cache, worker backpressure
Wave C: system/config/theme/plugins/MPRIS/application
Wave D: UI, utils, domain, service composition
```

- [ ] **Step 4: Record skips instead of forcing speculative changes**

```text
For each report item, validate current code first.
If the issue is already fixed, is a false positive, or is not justified, skip it and record the reason in the final summary.
Do not create placeholder commits for skipped items.
```

- [ ] **Step 5: Begin execution with Wave A**

```bash
sed -n '1,260p' docs/superpowers/plans/2026-04-10-optimization-report-wave-a-repositories-db.md
```

### Task 2: Execute Wave A Plan

**Files:**
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-a-repositories-db.md`

- [ ] **Step 1: Read the wave plan**

Run: `sed -n '1,320p' docs/superpowers/plans/2026-04-10-optimization-report-wave-a-repositories-db.md`
Expected: repository and database tasks cover critical query, transaction, and schema items.

- [ ] **Step 2: Implement each valid report item separately**

```text
Each numbered report item in Wave A gets its own test, validation, and commit.
Do not bundle adjacent fixes into a single commit even when they touch the same file.
```

- [ ] **Step 3: Keep commit messages report-aligned**

```bash
git commit -m "优化 1.1 曲目仓储读时写入"
git commit -m "优化 3.2 流派封面查询"
git commit -m "优化 7.1 数据库索引"
```

### Task 3: Execute Wave B Plan

**Files:**
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-b-audio-runtime.md`

- [ ] **Step 1: Read the wave plan**

Run: `sed -n '1,320p' docs/superpowers/plans/2026-04-10-optimization-report-wave-b-audio-runtime.md`
Expected: audio, mpv, HTTP, cache, and worker items are mapped to focused tests.

- [ ] **Step 2: Execute items in report order inside the wave**

```text
Finish 1.4 before later runtime tasks so queue backpressure behavior is stable during later verification.
Treat 1.2, 1.3, 2.6, 3.4, and 3.7 as separate commits even though they all touch audio_engine.py.
```

### Task 4: Execute Wave C Plan

**Files:**
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-c-system-services.md`

- [ ] **Step 1: Read the wave plan**

Run: `sed -n '1,360p' docs/superpowers/plans/2026-04-10-optimization-report-wave-c-system-services.md`
Expected: system-layer locking, caching, plugin, MPRIS, and application safety items are decomposed into isolated commits.

- [ ] **Step 2: Preserve behavior while hardening concurrency**

```text
Prefer small helper methods, dedicated locks, and cache invalidation points.
When a recommendation is not justified by the current implementation, skip it with a reason instead of widening the refactor.
```

### Task 5: Execute Wave D Plan

**Files:**
- Modify: `docs/superpowers/plans/2026-04-10-optimization-report-wave-d-ui-utils-domain.md`

- [ ] **Step 1: Read the wave plan**

Run: `sed -n '1,360p' docs/superpowers/plans/2026-04-10-optimization-report-wave-d-ui-utils-domain.md`
Expected: UI cleanup, utility performance, domain consistency, and service-composition items are broken into testable slices.

- [ ] **Step 2: Use the smallest possible validation for UI-heavy work**

```text
Prefer existing UI regression tests when behavior is already covered.
For purely rendering or responsiveness optimizations, verify behavior first and document any residual manual-performance risk.
```

### Task 6: Final Audit

**Files:**
- Modify: `docs/optimization-report-2026-04-10.md`

- [ ] **Step 1: Confirm all implemented items were committed separately**

Run: `git log --oneline --decorate -n 120`
Expected: one optimization commit per implemented report item, plus earlier planning commits that predate execution.

- [ ] **Step 2: Verify there are no accidental staged changes**

Run: `git status --short`
Expected: only intended remaining local files are present.

- [ ] **Step 3: Produce the final status summary**

```text
Report:
- implemented item numbers
- skipped item numbers with reasons
- tests run for each wave
- residual manual verification risks
```
