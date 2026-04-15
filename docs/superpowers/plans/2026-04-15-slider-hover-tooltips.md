# Slider Hover Tooltips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hover tooltips for playback progress time and volume percentage without changing existing slider interaction behavior.

**Architecture:** Reuse the shared `ClickableSlider` widget as the single hover-tooltip implementation point, then wire formatter callbacks from `PlayerControls` so progress formatting can depend on playback duration while volume formatting remains a simple percentage string. Keep tests focused on formatter behavior and existing seek helpers.

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: Add failing tests for slider formatter support

**Files:**
- Modify: `tests/test_ui/test_clickable_slider.py`
- Modify: `tests/test_ui/test_player_controls_seek_duration_fallback.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_clickable_slider_enables_mouse_tracking_for_hover_formatter():
    slider = ClickableSlider(Qt.Horizontal)
    slider.set_hover_tooltip_formatter(lambda value: f"{value}%")
    assert slider.hasMouseTracking() is True


def test_progress_hover_tooltip_formats_target_time():
    controls, _ = _make_controls(slider_value=500, duration_ms=200_000)
    assert controls._format_progress_hover_tooltip(250) == "0:50"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_clickable_slider.py tests/test_ui/test_player_controls_seek_duration_fallback.py -v`
Expected: FAIL because `ClickableSlider` and `PlayerControls` do not yet expose the hover tooltip helpers.

### Task 2: Implement shared slider hover tooltip support

**Files:**
- Modify: `ui/widgets/player_controls.py`
- Test: `tests/test_ui/test_clickable_slider.py`

- [ ] **Step 1: Write minimal implementation**

```python
class ClickableSlider(QSlider):
    def __init__(...):
        ...
        self._hover_tooltip_formatter = None

    def mouseMoveEvent(self, event):
        self._show_hover_tooltip(event)
        super().mouseMoveEvent(event)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_clickable_slider.py -v`
Expected: PASS

### Task 3: Wire progress and volume tooltip formatting

**Files:**
- Modify: `ui/widgets/player_controls.py`
- Test: `tests/test_ui/test_player_controls_seek_duration_fallback.py`

- [ ] **Step 1: Write minimal implementation**

```python
self._progress_slider.set_hover_tooltip_formatter(self._format_progress_hover_tooltip)
self._volume_slider.set_hover_tooltip_formatter(self._format_volume_hover_tooltip)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_player_controls_seek_duration_fallback.py -v`
Expected: PASS

### Task 4: Verify targeted regression coverage

**Files:**
- Modify: `ui/widgets/player_controls.py`
- Test: `tests/test_ui/test_clickable_slider.py`
- Test: `tests/test_ui/test_player_controls_seek_duration_fallback.py`

- [ ] **Step 1: Run focused verification**

Run: `uv run pytest tests/test_ui/test_clickable_slider.py tests/test_ui/test_player_controls_seek_duration_fallback.py tests/test_ui/test_player_controls_click_seek_race.py -v`
Expected: PASS

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-15-slider-hover-tooltips-design.md docs/superpowers/plans/2026-04-15-slider-hover-tooltips.md tests/test_ui/test_clickable_slider.py tests/test_ui/test_player_controls_seek_duration_fallback.py ui/widgets/player_controls.py
git commit -m "添加滑块悬停提示"
```
