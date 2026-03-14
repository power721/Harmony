"""
Tests for MatchScorer utility.
"""
import pytest
from utils.match_scorer import MatchScorer, TrackInfo, SearchResult


class TestMatchScorer:
    """Test MatchScorer functionality."""

    def test_exact_match(self):
        """Test exact match returns 100 score."""
        track = TrackInfo(title="晴天", artist="周杰伦", album="叶惠美", duration=269)
        result = SearchResult(title="晴天", artist="周杰伦", album="叶惠美", duration=269, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        assert score == 100.0

    def test_case_insensitive_match(self):
        """Test case insensitive matching."""
        track = TrackInfo(title="Hello", artist="World", album="Test", duration=180)
        result = SearchResult(title="hello", artist="world", album="test", duration=180, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        # Should be close to 100 (95% for case-insensitive match)
        assert score >= 90

    def test_partial_title_match(self):
        """Test partial title match."""
        track = TrackInfo(title="Hello World", artist="Artist", album="", duration=None)
        result = SearchResult(title="Hello World (Official Video)", artist="Artist", album="", duration=None, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        # Should match after normalization (normalized strings match)
        assert score >= 80

    def test_duration_match_within_tolerance(self):
        """Test duration match within tolerance."""
        track = TrackInfo(title="Song", artist="Artist", album="", duration=180)
        result = SearchResult(title="Song", artist="Artist", album="", duration=185, source="netease", id="1")  # 5 seconds difference

        score = MatchScorer.calculate_score(track, result)
        # Duration should still get full points
        assert score >= 90

    def test_duration_mismatch(self):
        """Test duration mismatch penalty."""
        track = TrackInfo(title="Song", artist="Artist", album="", duration=180)
        result = SearchResult(title="Song", artist="Artist", album="", duration=300, source="netease", id="1")  # 120 seconds difference

        score = MatchScorer.calculate_score(track, result)
        # Should have lower score due to duration mismatch
        assert score < 95

    def test_no_duration_info(self):
        """Test that missing duration doesn't penalize."""
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration=None)
        result = SearchResult(title="Song", artist="Artist", album="Album", duration=None, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        # Should get 50% duration score (neutral)
        assert score >= 85

    def test_find_best_match(self):
        """Test finding best match from multiple results."""
        track = TrackInfo(title="晴天", artist="周杰伦", album="叶惠美", duration=269)
        results = [
            SearchResult(title="晴天", artist="周杰伦", album="叶惠美", duration=269, source="netease", id="1"),
            SearchResult(title="晴天", artist="周杰伦", album="七里香", duration=300, source="netease", id="2"),
            SearchResult(title="晴天 (Live)", artist="周杰伦", album="", duration=280, source="netease", id="3"),
        ]

        best, score = MatchScorer.find_best_match(track, results)
        assert best.id == "1"
        assert score == 100.0

    def test_find_best_match_with_dicts(self):
        """Test finding best match with dict results."""
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration=180)
        results = [
            {'title': 'Wrong Song', 'artist': 'Wrong Artist', 'album': '', 'duration': None, 'source': 'netease', 'id': '1'},
            {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'duration': 180, 'source': 'netease', 'id': '2'},
        ]

        best, score = MatchScorer.find_best_match(track, results)
        # best is a SearchResult object after conversion
        assert best.id == '2'
        assert score == 100.0

    def test_empty_results(self):
        """Test with empty results list."""
        track = TrackInfo(title="Song", artist="Artist", album="", duration=None)
        result = MatchScorer.find_best_match(track, [])
        assert result is None

    def test_normalize_string(self):
        """Test string normalization."""
        # Test removing official video suffix
        assert MatchScorer._normalize_string("Hello (Official Video)") == "hello"
        assert MatchScorer._normalize_string("Hello [MV]") == "hello"
        assert MatchScorer._normalize_string("Hello - Official Audio") == "hello"

    def test_extract_main_artist(self):
        """Test extracting main artist from string."""
        assert MatchScorer._extract_main_artist("Artist A feat. Artist B") == "Artist A"
        assert MatchScorer._extract_main_artist("Artist A & Artist B") == "Artist A"
        assert MatchScorer._extract_main_artist("Artist A, Artist B") == "Artist A"
        assert MatchScorer._extract_main_artist("Single Artist") == "Single Artist"

    def test_word_overlap_score(self):
        """Test word overlap scoring."""
        score = MatchScorer._word_overlap_score("hello world", "hello world")
        assert score == 100.0

        score = MatchScorer._word_overlap_score("hello world", "hello")
        # 1 word overlap, 2 words total = 50%
        assert score == 50.0

    def test_chinese_matching(self):
        """Test Chinese character matching."""
        track = TrackInfo(title="稻香", artist="周杰伦", album="魔杰座", duration=223)
        result = SearchResult(title="稻香", artist="周杰伦", album="魔杰座", duration=223, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        assert score == 100.0
