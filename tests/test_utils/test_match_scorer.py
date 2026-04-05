"""
Tests for MatchScorer utility.
"""
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
        # With duration weight=40, missing duration (50% score) reduces total
        assert score >= 70

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
        """Test that missing duration doesn't penalize heavily."""
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration=None)
        result = SearchResult(title="Song", artist="Artist", album="Album", duration=None, source="netease", id="1")

        score = MatchScorer.calculate_score(track, result)
        # Should get 50% duration score (neutral), with new weights: 25+25+10+20=80
        assert score >= 80

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

    def test_lyrics_mode_duration_highest_weight(self):
        """Test lyrics mode where duration has highest weight."""
        track = TrackInfo(title="SongA", artist="ArtistA", album="AlbumA", duration=180)

        # Result with matching title but wrong album
        result1 = SearchResult(title="SongA", artist="ArtistA", album="AlbumB", duration=180, source="netease", id="1")
        # Result with wrong title but matching album
        result2 = SearchResult(title="SongB", artist="ArtistA", album="AlbumA", duration=180, source="netease", id="2")

        score1 = MatchScorer.calculate_score(track, result1, mode='lyrics')
        score2 = MatchScorer.calculate_score(track, result2, mode='lyrics')

        # In lyrics mode, title match should win (title weight=25, album weight=10)
        # result1: title=100, artist=100, album=50, duration=100 -> 25+25+5+40=95
        # result2: title=0, artist=100, album=100, duration=100 -> 0+25+10+40=75
        assert score1 > score2

    def test_cover_mode_album_highest_weight(self):
        """Test cover mode where album has highest weight."""
        track = TrackInfo(title="SongA", artist="ArtistA", album="AlbumA", duration=180)

        # Result with matching title but wrong album
        result1 = SearchResult(title="SongA", artist="ArtistA", album="AlbumB", duration=180, source="netease", id="1")
        # Result with wrong title but matching album
        result2 = SearchResult(title="SongB", artist="ArtistA", album="AlbumA", duration=180, source="netease", id="2")

        score1 = MatchScorer.calculate_score(track, result1, mode='cover')
        score2 = MatchScorer.calculate_score(track, result2, mode='cover')

        # In cover mode, album match should win (title weight=15, album weight=40)
        # result1: title=100, artist=100, album=50, duration=100 -> 15+25+20+20=80
        # result2: title=0, artist=100, album=100, duration=100 -> 0+25+40+20=85
        assert score2 > score1

    def test_find_best_match_with_mode(self):
        """Test find_best_match respects mode parameter."""
        track = TrackInfo(title="SongA", artist="ArtistA", album="AlbumA", duration=180)

        results = [
            SearchResult(title="SongA", artist="ArtistA", album="AlbumB", duration=180, source="netease", id="1"),
            SearchResult(title="SongB", artist="ArtistA", album="AlbumA", duration=180, source="netease", id="2"),
        ]

        # In lyrics mode, result1 should win (title match)
        best_lyrics, _ = MatchScorer.find_best_match(track, results, mode='lyrics')
        assert best_lyrics.id == "1"

        # In cover mode, result2 should win (album match)
        best_cover, _ = MatchScorer.find_best_match(track, results, mode='cover')
        assert best_cover.id == "2"

    def test_source_priority_tie_breaker(self):
        """Test that QQ Music has higher priority when scores are equal."""
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration=180)

        # Same track from different sources with identical scores
        results = [
            SearchResult(title="Song", artist="Artist", album="Album", duration=180, source="lrclib", id="1"),
            SearchResult(title="Song", artist="Artist", album="Album", duration=180, source="kugou", id="2"),
            SearchResult(title="Song", artist="Artist", album="Album", duration=180, source="netease", id="3"),
            SearchResult(title="Song", artist="Artist", album="Album", duration=180, source="qqmusic", id="4"),
        ]

        best, score = MatchScorer.find_best_match(track, results)
        # QQ Music should be selected despite same score
        assert best.source == "qqmusic"
        assert best.id == "4"

    def test_source_priority_with_different_scores(self):
        """Test that higher score still wins over source priority."""
        track = TrackInfo(title="SongA", artist="Artist", album="Album", duration=180)

        results = [
            SearchResult(title="SongB", artist="Artist", album="Album", duration=180, source="qqmusic", id="1"),
            SearchResult(title="SongA", artist="Artist", album="Album", duration=180, source="netease", id="2"),
        ]

        best, score = MatchScorer.find_best_match(track, results)
        # NetEase should win because it has higher score (exact title match)
        assert best.source == "netease"
        assert best.id == "2"


class TestTitleScoreWithDictAndList:
    """Test _title_score with dict and list inputs."""

    def test_title_score_dict_input(self):
        """Test _title_score when result_title is a dict with 'title' key."""
        track_title = "Hello World"
        result_title = {"title": "Hello World"}
        score = MatchScorer._title_score(track_title, result_title)
        assert score == 100.0

    def test_title_score_dict_with_name_key(self):
        """Test _title_score when dict has 'name' key instead of 'title'."""
        track_title = "Hello World"
        result_title = {"name": "Hello World"}
        score = MatchScorer._title_score(track_title, result_title)
        assert score == 100.0

    def test_title_score_dict_empty(self):
        """Test _title_score when dict has no matching keys."""
        track_title = "Hello World"
        result_title = {"other": "value"}
        score = MatchScorer._title_score(track_title, result_title)
        assert score == 0.0

    def test_title_score_list_input(self):
        """Test _title_score when result_title is a list."""
        track_title = "Hello World"
        result_title = ["Hello World", "Alternative"]
        score = MatchScorer._title_score(track_title, result_title)
        assert score == 100.0

    def test_title_score_list_empty(self):
        """Test _title_score when list is empty."""
        track_title = "Hello World"
        result_title = []
        score = MatchScorer._title_score(track_title, result_title)
        assert score == 0.0


class TestArtistScoreWithList:
    """Test _artist_score with list input."""

    def test_artist_score_list_input(self):
        """Test _artist_score when result_artist is a list."""
        score = MatchScorer._artist_score("Artist", ["Artist", "Other"])
        # List is joined with ", " so result becomes "Artist, Other"
        # After normalization comma is removed -> "artist other"
        # "artist" is contained in "artist other" -> partial match = 70
        assert score == 70.0

    def test_artist_score_list_empty(self):
        """Test _artist_score when list is empty."""
        score = MatchScorer._artist_score("Artist", [])
        assert score == 0.0

    def test_artist_score_list_with_none_values(self):
        """Test _artist_score when list contains None values."""
        score = MatchScorer._artist_score("Artist", [None, "Artist"])
        # Non-None values are joined, None is filtered out
        assert score >= 90.0


class TestAlbumScoreWithDictAndList:
    """Test _album_score with dict and list inputs."""

    def test_album_score_dict_input(self):
        """Test _album_score when result_album is a dict."""
        track_album = "My Album"
        result_album = {"name": "My Album"}
        score = MatchScorer._album_score(track_album, result_album)
        assert score == 100.0

    def test_album_score_dict_with_title_key(self):
        """Test _album_score when dict has 'title' key."""
        track_album = "My Album"
        result_album = {"title": "My Album"}
        score = MatchScorer._album_score(track_album, result_album)
        assert score == 100.0

    def test_album_score_dict_empty(self):
        """Test _album_score when dict has no matching keys."""
        track_album = "My Album"
        result_album = {"other": "value"}
        score = MatchScorer._album_score(track_album, result_album)
        # No album info - don't penalize
        assert score == 50.0

    def test_album_score_list_input(self):
        """Test _album_score when result_album is a list."""
        track_album = "My Album"
        result_album = ["My Album", "Other"]
        score = MatchScorer._album_score(track_album, result_album)
        # List is joined with ", " so result becomes "My Album, Other"
        # "My Album" is contained in "My Album, Other" -> partial match = 70
        assert score == 70.0

    def test_album_score_list_empty(self):
        """Test _album_score when list is empty."""
        score = MatchScorer._album_score("Album", [])
        assert score == 50.0


class TestSourcePriority:
    """Test SOURCE_PRIORITY tie-breaking."""

    def test_qqmusic_highest_priority(self):
        """Test QQ Music has lowest priority number (highest priority)."""
        assert MatchScorer.SOURCE_PRIORITY['qqmusic'] == 0

    def test_source_priority_order(self):
        """Test source priority order is correct."""
        assert MatchScorer.SOURCE_PRIORITY['qqmusic'] < MatchScorer.SOURCE_PRIORITY['netease']
        assert MatchScorer.SOURCE_PRIORITY['netease'] < MatchScorer.SOURCE_PRIORITY['kugou']
        assert MatchScorer.SOURCE_PRIORITY['kugou'] < MatchScorer.SOURCE_PRIORITY['lrclib']

    def test_unknown_source_default_priority(self):
        """Test unknown source gets default priority 99."""
        assert MatchScorer.SOURCE_PRIORITY.get('unknown_source', 99) == 99


class TestNoneAndEmptyStringHandling:
    """Test score methods with None and empty strings."""

    def test_title_score_none_track_title(self):
        """Test _title_score with None track title."""
        score = MatchScorer._title_score(None, "Song")
        assert score == 0.0

    def test_title_score_none_result_title(self):
        """Test _title_score with None result title."""
        score = MatchScorer._title_score("Song", None)
        assert score == 0.0

    def test_title_score_empty_track_title(self):
        """Test _title_score with empty track title."""
        score = MatchScorer._title_score("", "Song")
        assert score == 0.0

    def test_title_score_empty_result_title(self):
        """Test _title_score with empty result title."""
        score = MatchScorer._title_score("Song", "")
        assert score == 0.0

    def test_title_score_both_empty(self):
        """Test _title_score with both empty strings."""
        score = MatchScorer._title_score("", "")
        assert score == 0.0

    def test_artist_score_none_track_artist(self):
        """Test _artist_score with None track artist."""
        score = MatchScorer._artist_score(None, "Artist")
        assert score == 0.0

    def test_artist_score_none_result_artist(self):
        """Test _artist_score with None result artist."""
        score = MatchScorer._artist_score("Artist", None)
        assert score == 0.0

    def test_artist_score_empty_strings(self):
        """Test _artist_score with empty strings."""
        score = MatchScorer._artist_score("", "")
        assert score == 0.0

    def test_album_score_none_track_album(self):
        """Test _album_score with None track album."""
        # No album info - don't penalize
        score = MatchScorer._album_score(None, "Album")
        assert score == 50.0

    def test_album_score_none_result_album(self):
        """Test _album_score with None result album."""
        score = MatchScorer._album_score("Album", None)
        assert score == 50.0

    def test_album_score_both_empty(self):
        """Test _album_score with both empty strings."""
        score = MatchScorer._album_score("", "")
        assert score == 50.0

    def test_album_score_one_empty(self):
        """Test _album_score with one side empty."""
        score = MatchScorer._album_score("", "Album")
        assert score == 50.0

        score = MatchScorer._album_score("Album", "")
        assert score == 50.0
