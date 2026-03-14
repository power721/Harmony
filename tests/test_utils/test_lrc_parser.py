"""
Tests for LRC parser utility.
"""

import pytest
from utils.lrc_parser import (
    LyricLine,
    parse_lrc,
    parse_words,
    TIME_RE,
    META_RE,
    WORD_RE,
)


class TestLyricLine:
    """Test LyricLine class."""

    def test_initialization(self):
        """Test LyricLine initialization."""
        line = LyricLine(time=10.5, text="Hello World")
        assert line.time == 10.5
        assert line.text == "Hello World"
        assert line.words == []

    def test_initialization_with_words(self):
        """Test LyricLine with words."""
        words = [(0.1, 0.2, "Hello"), (0.3, 0.4, "World")]
        line = LyricLine(time=10.5, text="Hello World", words=words)
        assert line.words == words

    def test_repr(self):
        """Test LyricLine string representation."""
        line = LyricLine(time=10.5, text="Hello World")
        repr_str = repr(line)
        assert "LyricLine" in repr_str
        assert "10.50" in repr_str
        assert "Hello World" in repr_str


class TestRegexPatterns:
    """Test regex patterns."""

    def test_time_regex_basic(self):
        """Test TIME_RE with basic format."""
        match = TIME_RE.match("[01:23.45]")
        assert match is not None
        assert match.group(1) == "01"
        assert match.group(2) == "23.45"

    def test_time_regex_no_decimal(self):
        """Test TIME_RE without decimal."""
        match = TIME_RE.match("[01:23]")
        assert match is not None
        assert match.group(1) == "01"
        assert match.group(2) == "23"

    def test_meta_regex(self):
        """Test META_RE pattern."""
        match = META_RE.match("[ti:Song Title]")
        assert match is not None
        assert match.group(1).lower() == "ti"
        assert match.group(2) == "Song Title"

    def test_meta_regex_case_insensitive(self):
        """Test META_RE is case insensitive."""
        match = META_RE.match("[TI:Song Title]")
        assert match is not None

    def test_meta_regex_different_keys(self):
        """Test META_RE with different metadata keys."""
        keys = ["ti", "ar", "al", "by", "offset"]
        for key in keys:
            match = META_RE.match(f"[{key}:value]")
            assert match is not None
            assert match.group(1).lower() == key

    def test_word_regex(self):
        """Test WORD_RE pattern."""
        match = WORD_RE.match("<100,200,0>Hello")
        assert match is not None
        assert match.group(1) == "100"
        assert match.group(2) == "200"
        assert match.group(3) == "Hello"


class TestParseWords:
    """Test parse_words function."""

    def test_parse_basic_words(self):
        """Test parsing basic word-by-word lyrics."""
        text = "<100,200,0>Hello<300,400,0>World"
        words = parse_words(text)

        assert len(words) == 2
        assert words[0] == (0.1, 0.2, "Hello")
        assert words[1] == (0.3, 0.4, "World")

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        words = parse_words("")
        assert words == []

    def test_parse_no_word_tags(self):
        """Test parsing text without word tags."""
        words = parse_words("Just plain text")
        assert words == []

    def test_parse_mixed_content(self):
        """Test parsing mixed word tags and text."""
        text = "<100,200,0>Word1<300,400,0>Word2 extra"
        words = parse_words(text)

        assert len(words) == 2
        assert words[0][2] == "Word1"
        assert words[1][2] == "Word2 extra"  # Text after tag is included


class TestParseLrc:
    """Test parse_lrc function."""

    def test_parse_simple_lrc(self):
        """Test parsing simple LRC format."""
        lrc_text = """[00:01.00]First line
[00:03.00]Second line
[00:05.00]Third line"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 3
        assert lyrics[0].time == 1.0
        assert lyrics[0].text == "First line"
        assert lyrics[1].time == 3.0
        assert lyrics[1].text == "Second line"
        assert lyrics[2].time == 5.0
        assert lyrics[2].text == "Third line"

    def test_parse_lrc_with_metadata(self):
        """Test parsing LRC with metadata tags."""
        lrc_text = """[ti:Song Title]
[ar:Artist Name]
[al:Album Name]
[00:01.00]Lyric line"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].time == 1.0
        assert lyrics[0].text == "Lyric line"
        # Note: Current implementation returns only lyrics, metadata is ignored

    def test_parse_lrc_with_empty_lines(self):
        """Test parsing LRC with empty lines."""
        lrc_text = """[00:01.00]First line

[00:03.00]Second line"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].text == "First line"
        assert lyrics[1].text == "Second line"

    def test_parse_lrc_with_multiple_times(self):
        """Test parsing LRC with multiple timestamps for same line."""
        lrc_text = """[00:01.00][00:02.00]Same line"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].time == 1.0
        assert lyrics[0].text == "Same line"
        assert lyrics[1].time == 2.0
        assert lyrics[1].text == "Same line"

    def test_parse_lrc_preserves_order(self):
        """Test that lyrics are sorted by time."""
        lrc_text = """[00:05.00]Third
[00:01.00]First
[00:03.00]Second"""

        lyrics = parse_lrc(lrc_text)

        assert lyrics[0].text == "First"
        assert lyrics[1].text == "Second"
        assert lyrics[2].text == "Third"
        assert lyrics[0].time == 1.0
        assert lyrics[1].time == 3.0
        assert lyrics[2].time == 5.0

    def test_parse_lrc_with_word_by_word(self):
        """Test parsing LRC with word-by-word lyrics."""
        lrc_text = """[00:01.00]<100,200,0>Hello<300,400,0>World"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "HelloWorld"  # Words concatenated
        assert len(lyrics[0].words) == 2
        assert lyrics[0].words[0] == (0.1, 0.2, "Hello")

    def test_parse_empty_lrc(self):
        """Test parsing empty LRC."""
        lyrics = parse_lrc("")
        assert lyrics == []

    def test_parse_lrc_without_tags(self):
        """Test parsing LRC without time tags."""
        lrc_text = """Random text
Another line"""

        lyrics = parse_lrc(lrc_text)
        assert lyrics == []

    def test_parse_lrc_with_decimal_times(self):
        """Test parsing LRC with decimal seconds."""
        lrc_text = """[00:01.50]One and a half seconds"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].time == 1.5

    def test_parse_lric_without_text(self):
        """Test parsing LRC lines without text content."""
        lrc_text = """[00:01.00]
[00:02.00]Some text"""

        lyrics = parse_lrc(lrc_text)

        # First line has space as text
        assert lyrics[0].text == " "
        assert lyrics[1].text == "Some text"

    def test_parse_lric_only_metadata(self):
        """Test parsing LRC with only metadata."""
        lrc_text = """[ti:Song Title]
[ar:Artist]"""

        lyrics = parse_lrc(lrc_text)
        assert len(lyrics) == 0


class TestParseCharWordLrc:
    """Test parsing character-word lyrics format."""

    def test_parse_char_word_format(self):
        """Test parsing character-word lyrics format."""
        lrc_text = """[00:00.00]<00:00.000>青<00:00.366>花<00:00.732>瓷
[00:05.49]<00:05.490>词<00:06.588>：<00:07.686>方<00:08.784>文<00:09.882>山"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 2

        # First line
        assert lyrics[0].time == 0.0
        assert lyrics[0].text == "青花瓷"
        assert len(lyrics[0].words) == 3
        assert lyrics[0].words[0] == (0.0, 0.366, "青")
        assert lyrics[0].words[1] == (0.366, 0.366, "花")
        assert lyrics[0].words[2] == (0.732, 1.0, "瓷")

        # Second line
        assert lyrics[1].time == 5.49
        assert lyrics[1].text == "词：方文山"
        assert len(lyrics[1].words) == 5

    def test_parse_char_word_with_spaces(self):
        """Test parsing character-word lyrics with spaces and symbols."""
        lrc_text = """[00:00.00]<00:00.000>青<00:00.366>花<00:00.732>瓷<00:01.098> <00:01.464>-<00:01.830> <00:02.196>周<00:02.562>杰<00:02.928>伦"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "青花瓷 - 周杰伦"
        assert len(lyrics[0].words) == 9
        # Check space character
        assert lyrics[0].words[3][2] == " "
        # Check dash
        assert lyrics[0].words[4][2] == "-"

    def test_parse_char_word_with_english(self):
        """Test parsing character-word lyrics with English text."""
        lrc_text = """[00:00.00]<00:00.000>(<00:01.000>Jay<00:02.000> <00:03.000>Chou<00:04.000>)"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "(Jay Chou)"
        assert len(lyrics[0].words) == 5
        assert lyrics[0].words[0][2] == "("
        assert lyrics[0].words[1][2] == "Jay"
        assert lyrics[0].words[2][2] == " "
        assert lyrics[0].words[3][2] == "Chou"
        assert lyrics[0].words[4][2] == ")"

    def test_parse_char_word_empty_lines(self):
        """Test parsing character-word lyrics with empty lines."""
        lrc_text = """[00:00.00]<00:00.000>青<00:00.366>花

[00:05.49]<00:05.490>词<00:06.588>："""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].text == "青花"
        assert lyrics[1].text == "词："
