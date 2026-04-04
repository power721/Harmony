# Requests Network Layer Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the repo's `requests` usage behind shared `HttpClient` primitives so sessions, adapters, timeouts, and streamed-response cleanup are configured in one place.

**Architecture:** Extend `infrastructure.network.HttpClient` to own session construction and reusable shared clients. Migrate service-layer raw `requests.get()` and ad-hoc `requests.Session()` usage onto that client, leaving UI-only call sites for a smaller follow-up if needed.

**Tech Stack:** Python, `requests`, `urllib3` via `requests.adapters.HTTPAdapter`, pytest

---

### Task 1: Strengthen Shared HTTP Primitives

**Files:**
- Modify: `infrastructure/network/http_client.py`
- Test: `tests/test_infrastructure/test_http_client.py`

- [ ] Add regression tests for adapter pool sizing, shared-client reuse, and stream cleanup.
- [ ] Run the targeted `pytest` slice and confirm the new tests fail against the current implementation.
- [ ] Implement shared session creation, adapter mounting, and safe streaming helpers in `HttpClient`.
- [ ] Re-run the `HttpClient` tests and confirm they pass.

### Task 2: Move Service-Layer Call Sites Onto HttpClient

**Files:**
- Modify: `services/cloud/share_search_service.py`
- Modify: `services/lyrics/lyrics_service.py`
- Modify: `services/lyrics/lyrics_loader.py`
- Modify: `services/lyrics/qqmusic_lyrics.py`
- Modify: `services/online/online_music_service.py`
- Modify: `services/online/download_service.py`
- Modify: `services/cloud/download_service.py`
- Modify: `services/cloud/baidu_service.py`
- Modify: `services/cloud/quark_service.py`
- Test: `tests/test_services/test_share_search_service.py`
- Test: `tests/test_services/test_online_download_service.py`

- [ ] Update service modules to stop creating raw `requests.Session()` objects directly.
- [ ] Replace service-level `requests.get()` calls with `HttpClient` requests or `HttpClient.stream(...)`.
- [ ] Preserve existing request headers and per-call timeout overrides while routing through the shared client.
- [ ] Ensure all stream/download paths close responses deterministically.
- [ ] Update affected tests to patch the shared `HttpClient` path instead of raw `requests.get`.

### Task 3: Verify and Report Remaining Direct Requests

**Files:**
- Modify as needed based on verification results

- [ ] Run targeted infrastructure and service pytest slices for touched modules.
- [ ] Run a final `rg` audit for remaining direct `requests` calls.
- [ ] Report which remaining direct calls were intentionally left outside this pass, if any.
