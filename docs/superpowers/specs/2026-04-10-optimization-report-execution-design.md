# 2026-04-10 Optimization Report Execution Design

## Context

This design covers the implementation strategy for `docs/optimization-report-2026-04-10.md`.
The report contains 81 numbered items spanning repositories, database, audio playback,
system services, UI, utility modules, and domain models. The user requires two hard
constraints:

1. Every valid report item must be handled as an isolated change set.
2. Every implemented report item must be committed separately.

The worktree is already dirty with unrelated local changes (`.python-version`) and the
report file itself is currently untracked, so execution must avoid absorbing unrelated
files into commits.

## Goal

Execute the optimization report end-to-end while keeping change isolation strict, commit
granularity aligned to report items, and verification attached to each implemented item.

## Scope Rules

### Included

- Only items listed in `docs/optimization-report-2026-04-10.md`
- Code, tests, and narrowly scoped docs required to implement and verify each item

### Excluded

- Unrelated cleanup discovered during implementation
- User-local workspace changes unrelated to the targeted report item
- Refactors larger than the reported issue unless required to make the item correct

### Skip Policy

Each report item must be revalidated against the current code before implementation.
If an item is already fixed, is a false positive, or is not justified in the current
architecture, it will be skipped and recorded in the final summary with a concrete reason.
Skipped items do not get placeholder commits.

## Execution Model

### Primary Strategy

Execution will proceed in subsystem waves to reduce context switching and merge risk, but
commit boundaries will remain one report item per commit.

Recommended wave order:

1. Repository, database, and input-validation items
2. Audio engine, mpv backend, download, and cache items
3. `system/` concurrency, config, plugin, event bus, hotkey, and MPRIS items
4. UI responsiveness, cleanup, utility, duplicated-code, and domain-model items

This ordering is operational only. It does not change item numbering, reporting, or
commit granularity.

### Per-Item Workflow

For each report item:

1. Re-read the target code and confirm the issue is still real.
2. Identify the narrowest code surface that fixes only that item.
3. Add or update focused tests when feasible.
4. Run targeted verification.
5. Commit only the files required for that item.

No commit may intentionally include changes for two different report items, even when
they touch the same file.

## Change Boundaries

### Allowed Multi-File Changes

A single report item may touch multiple files when necessary, for example:

- implementation file + targeted tests
- shared helper extraction required only for that item
- schema or migration change + repository consumer updates

### Disallowed Bundling

The following must remain separate:

- independent report items from the same section
- opportunistic cleanup found while editing
- style-only changes not required by the item

## Verification Policy

Every implemented item must have at least one concrete verification step before commit.

Verification preference:

1. Existing focused pytest target
2. New focused pytest case when the bug is testable
3. Closest stable regression test suite when the issue is UI-thread or concurrency-heavy
4. Manual reasoning note only when automation is not practical, with residual risk stated

Verification must stay proportional. The goal is evidence for the specific item, not
rerunning the whole application after every commit.

## Risk Management

### Dirty Worktree

Unrelated files must never be staged accidentally. Each commit should stage explicit paths
only. Existing local modifications must be preserved.

### Shared Files Across Multiple Items

Several dense modules appear repeatedly in the report, especially:

- `infrastructure/audio/audio_engine.py`
- `system/config.py`
- `infrastructure/database/sqlite_manager.py`
- `infrastructure/audio/mpv_backend.py`
- `system/theme.py`

When a later item touches a previously edited file, the new change must be layered on top
of prior item commits without rewriting earlier behavior or silently folding multiple items
together.

### Suggestion-Style Items

Some report entries are recommendations rather than proven defects. These need explicit
revalidation before any code change. If the evidence is weak, the item should be skipped
instead of forcing speculative churn.

## Testing Strategy by Area

### Repository and Database Items

- Prefer `tests/test_repositories/` and `tests/test_infrastructure/`
- Add regression tests around query count, rollback behavior, and schema expectations

### Audio and Concurrency Items

- Prefer focused unit tests where locking or helper behavior can be isolated
- Use targeted playback/infrastructure tests for regression coverage
- If thread timing makes tests unstable, validate the smallest deterministic helper layer

### System and Plugin Items

- Prefer `tests/test_system/` and `tests/test_plugins/`
- Cover lock behavior, cache invalidation, and cleanup semantics where practical

### UI and Utility Items

- Prefer `tests/test_ui/` and `tests/test_utils/`
- For UI performance optimizations, validate behavior preservation first and document any
  remaining manual-performance risk

## Deliverables

The final execution outcome should include:

- one commit per implemented report item
- a list of skipped items with reasons
- a concise summary of residual risks for items that could not be fully automated

## Non-Goals

- Producing a single umbrella optimization commit
- Normalizing unrelated style inconsistencies project-wide
- Rewriting architecture beyond what the report item requires
