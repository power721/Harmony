"""
Tests for bug fix: Bug 14 - Incomplete priority scoring in dedup module.

Previously, a track with both has_special_version=True AND has_instrumental=True
fell through to fallback score 50, lower than either flag alone (70 or 60).
"""

from utils.dedup import extract_version_info


class TestBug14DedupPriorityScoring:
    """Bug 14: Combined flag priority scores should be correct."""

    def test_special_only(self):
        """Special version only should score 70."""
        info = extract_version_info("Song (纯享版)")
        assert info.has_special_version is True
        assert info.has_instrumental is False
        assert info.priority_score == 70

    def test_instrumental_only(self):
        """Instrumental only should score 60."""
        info = extract_version_info("Song (伴奏)")
        assert info.has_instrumental is True
        assert info.has_special_version is False
        assert info.priority_score == 60

    def test_special_plus_instrumental(self):
        """Special + instrumental should score 55, not 50."""
        info = extract_version_info("Song (吟唱版伴奏)")
        assert info.has_special_version is True
        assert info.has_instrumental is True
        assert info.priority_score == 55

    def test_special_plus_instrumental_higher_than_either_alone(self):
        """Special+instrumental score should be higher than falling to 50."""
        info = extract_version_info("Song (纯享版伴奏)")
        assert info.priority_score == 55
        assert info.priority_score > 50  # Was 50 before fix

    def test_special_plus_instrumental_lower_than_either_alone(self):
        """Combined score should be lower than either flag alone."""
        info = extract_version_info("Song (remix伴奏)")
        assert 60 > info.priority_score == 55 > 50

    def test_original_still_highest(self):
        """Original version should still have highest priority."""
        info = extract_version_info("Song")
        assert info.priority_score == 100

    def test_live_instrumental_still_40(self):
        """Live + instrumental should still be 40."""
        info = extract_version_info("Song (Live伴奏)")
        assert info.is_live is True
        assert info.has_instrumental is True
        assert info.priority_score == 40

    def test_harmony_still_lowest(self):
        """Harmony should still be lowest priority."""
        info = extract_version_info("Song (和声伴奏)")
        assert info.has_harmony is True
        assert info.priority_score == 20
