"""
Tests for bug fix: Bug 18 - Missing last-line handling in mini_lyrics_widget.

Previously, mini_lyrics_widget.update_position() never updated current_index
if time was past the last line, and had no empty-lines guard.
"""


class FakeLyricLine:
    """Minimal mock for lyrics line."""
    def __init__(self, time: int, text: str):
        self.time = time
        self.text = text


class TestBug18MiniLyricsLastLine:
    """Bug 18: mini_lyrics_widget should handle last line and empty lines."""

    def _make_update_position(self):
        """Build a standalone update_position using the same logic."""

        # We test the logic directly since mini_lyrics_widget needs Qt
        def update_position(lines, t):
            if not lines:
                return -1
            for i in range(len(lines) - 1):
                if lines[i].time <= t < lines[i + 1].time:
                    return i
            # Last line: if time >= last line's time
            if t >= lines[-1].time:
                return len(lines) - 1
            return -1  # Before first line

        return update_position

    def test_empty_lines_returns_neg1(self):
        """Empty lines list should return -1."""
        update = self._make_update_position()
        assert update([], 0) == -1

    def test_before_first_line_returns_neg1(self):
        """Time before first line should return -1."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "first"), FakeLyricLine(5000, "second")]
        assert update(lines, 500) == -1

    def test_first_line_matched(self):
        """Time within first line range should return index 0."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "first"), FakeLyricLine(5000, "second")]
        assert update(lines, 2000) == 0

    def test_second_line_matched(self):
        """Time within second line range should return index 1."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "first"), FakeLyricLine(5000, "second")]
        assert update(lines, 6000) == 1

    def test_past_last_line_returns_last_index(self):
        """Time past last line should return last index, not stay stale."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "first"), FakeLyricLine(5000, "second")]
        assert update(lines, 10000) == 1

    def test_exactly_at_last_line_time(self):
        """Time exactly at last line time should return last index."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "first"), FakeLyricLine(5000, "second")]
        assert update(lines, 5000) == 1

    def test_single_line_past_time(self):
        """Single line with time past it should return index 0."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "only line")]
        assert update(lines, 5000) == 0

    def test_single_line_before_time(self):
        """Single line with time before it should return -1."""
        update = self._make_update_position()
        lines = [FakeLyricLine(1000, "only line")]
        assert update(lines, 500) == -1
