# QQMusic Play Current List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make QQ online-song double-click and context-menu `play` queue the full current list and start from the chosen song.

**Architecture:** Reuse the existing `play_online_tracks` signal as the single whole-list playback path. Add one helper in `OnlineMusicView` that resolves a track or selection to a start index in `self._current_tracks`, then update all QQ current-list play entry points to use it.

**Tech Stack:** Python 3.12, PySide6 signals/widgets, pytest, pytest-qt

---

### Task 1: Lock the new play semantics with tests

**Files:**
- Modify: `tests/test_ui/test_online_music_view_focus.py`
- Test: `tests/test_ui/test_online_music_view_focus.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ranking_track_activation_plays_current_list_from_selected_index():
    view = OnlineMusicView.__new__(OnlineMusicView)
    track_a = SimpleNamespace(mid="a")
    track_b = SimpleNamespace(mid="b")
    emitted = []
    view._current_tracks = [track_a, track_b]
    view.play_online_tracks = SimpleNamespace(
        emit=lambda start_index, tracks: emitted.append((start_index, tracks))
    )
    view._build_tracks_payload = lambda tracks: [(track.mid, {}) for track in tracks]

    OnlineMusicView._on_ranking_track_activated(view, track_b)

    assert emitted == [(1, [("a", {}), ("b", {})])]


def test_play_selected_tracks_plays_current_list_from_first_selected_track():
    view = OnlineMusicView.__new__(OnlineMusicView)
    track_a = SimpleNamespace(mid="a")
    track_b = SimpleNamespace(mid="b")
    track_c = SimpleNamespace(mid="c")
    emitted = []
    view._current_tracks = [track_a, track_b, track_c]
    view.play_online_tracks = SimpleNamespace(
        emit=lambda start_index, tracks: emitted.append((start_index, tracks))
    )
    view._build_tracks_payload = lambda tracks: [(track.mid, {}) for track in tracks]

    OnlineMusicView._play_selected_tracks(view, [track_b, track_c])

    assert emitted == [(1, [("a", {}), ("b", {}), ("c", {})])]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_online_music_view_focus.py -k "ranking_track_activation or play_selected_tracks" -vv`
Expected: FAIL because ranking activation still calls `_play_track()` and selected-track play still plays only the selected subset.

- [ ] **Step 3: Write minimal implementation**

```python
def _play_current_tracks_from_index(self, start_index: int):
    if start_index < 0 or start_index >= len(self._current_tracks):
        return
    self.play_online_tracks.emit(start_index, self._build_tracks_payload(self._current_tracks))


def _play_current_tracks_from_track(self, track: OnlineTrack):
    if not track:
        return
    for index, current_track in enumerate(self._current_tracks):
        if current_track is track:
            self._play_current_tracks_from_index(index)
            return
        if getattr(current_track, "mid", None) and getattr(current_track, "mid", None) == getattr(track, "mid", None):
            self._play_current_tracks_from_index(index)
            return


def _play_selected_tracks(self, tracks: List[OnlineTrack]):
    if not tracks:
        return
    self._play_current_tracks_from_track(tracks[0])


def _on_ranking_track_activated(self, track):
    self._play_current_tracks_from_track(track)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_online_music_view_focus.py -k "ranking_track_activation or play_selected_tracks" -vv`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_online_music_view_focus.py plugins/builtin/qqmusic/lib/online_music_view.py docs/superpowers/specs/2026-04-09-qqmusic-play-current-list-design.md docs/superpowers/plans/2026-04-09-qqmusic-play-current-list.md
git commit -m "统一在线歌曲播放队列行为"
```
