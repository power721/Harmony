"""
Tests for LRC parser utility.
"""

import pytest
from utils.lrc_parser import (
    LyricLine,
    LyricWord,
    parse_lrc,
    parse_words,
    parse_yrc,
    parse_qrc,
    detect_and_parse,
    detect_format,
    TIME_RE,
    META_RE,
    WORD_RE,
    YRC_LINE_RE,
    YRC_WORD_RE,
    QRC_LINE_RE,
    QRC_WORD_RE,
    QRC_XML_RE,
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
        assert isinstance(words[0], LyricWord)
        assert words[0].time == 0.1
        assert words[0].duration == 0.2
        assert words[0].text == "Hello"
        assert words[1].time == 0.3
        assert words[1].duration == 0.4
        assert words[1].text == "World"

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
        assert words[0].text == "Word1"
        assert words[1].text == "Word2 extra"  # Text after tag is included


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
        assert isinstance(lyrics[0].words[0], LyricWord)
        assert lyrics[0].words[0].time == 0.1
        assert lyrics[0].words[0].duration == 0.2
        assert lyrics[0].words[0].text == "Hello"

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
        assert isinstance(lyrics[0].words[0], LyricWord)
        assert lyrics[0].words[0].time == 0.0
        assert lyrics[0].words[0].duration == 0.366
        assert lyrics[0].words[0].text == "青"
        assert lyrics[0].words[1].time == 0.366
        assert lyrics[0].words[1].text == "花"
        assert lyrics[0].words[2].time == 0.732
        assert lyrics[0].words[2].text == "瓷"

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
        assert lyrics[0].words[3].text == " "
        # Check dash
        assert lyrics[0].words[4].text == "-"

    def test_parse_char_word_with_english(self):
        """Test parsing character-word lyrics with English text."""
        lrc_text = """[00:00.00]<00:00.000>(<00:01.000>Jay<00:02.000> <00:03.000>Chou<00:04.000>)"""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "(Jay Chou)"
        assert len(lyrics[0].words) == 5
        assert lyrics[0].words[0].text == "("
        assert lyrics[0].words[1].text == "Jay"
        assert lyrics[0].words[2].text == " "
        assert lyrics[0].words[3].text == "Chou"
        assert lyrics[0].words[4].text == ")"

    def test_parse_char_word_empty_lines(self):
        """Test parsing character-word lyrics with empty lines."""
        lrc_text = """[00:00.00]<00:00.000>青<00:00.366>花

[00:05.49]<00:05.490>词<00:06.588>："""

        lyrics = parse_lrc(lrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].text == "青花"
        assert lyrics[1].text == "词："


class TestParseYrc:
    """Test parsing YRC (NetEase word-by-word) lyrics format."""

    def test_parse_basic_yrc(self):
        """Test parsing basic YRC format."""
        yrc_text = """[1234,567](123,45,0)嘿(234,45,0)等(345,45,0)我"""

        lyrics = parse_yrc(yrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].time == 1.234  # 1234ms = 1.234s
        assert lyrics[0].duration == 0.567  # 567ms = 0.567s
        assert lyrics[0].text == "嘿等我"
        assert len(lyrics[0].words) == 3

        # First word: line_time + offset = 1234 + 123 = 1357ms = 1.357s
        assert lyrics[0].words[0].time == 1.357
        assert lyrics[0].words[0].duration == 0.045
        assert lyrics[0].words[0].text == "嘿"

        # Second word: 1234 + 234 = 1468ms
        assert lyrics[0].words[1].time == 1.468
        assert lyrics[0].words[1].text == "等"

        # Third word: 1234 + 345 = 1579ms
        assert lyrics[0].words[2].time == 1.579
        assert lyrics[0].words[2].text == "我"

    def test_parse_yrc_multiple_lines(self):
        """Test parsing YRC with multiple lines."""
        yrc_text = """[1000,2000](0,500,0)Hello(500,500,0)World
[4000,3000](0,1000,0)Test(1000,1000,0)Line"""

        lyrics = parse_yrc(yrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].time == 1.0
        assert lyrics[0].text == "HelloWorld"
        assert lyrics[1].time == 4.0
        assert lyrics[1].text == "TestLine"

    def test_parse_yrc_empty(self):
        """Test parsing empty YRC."""
        assert parse_yrc("") == []
        assert parse_yrc(None) == []

    def test_parse_yrc_with_chinese(self):
        """Test parsing YRC with Chinese characters."""
        yrc_text = """[0,5000](0,500,0)青(500,500,0)花(1000,500,0)瓷"""

        lyrics = parse_yrc(yrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "青花瓷"
        assert lyrics[0].words[0].text == "青"
        assert lyrics[0].words[1].text == "花"
        assert lyrics[0].words[2].text == "瓷"


class TestDetectAndParse:
    """Test auto-detection and parsing of lyrics format."""

    def test_detect_yrc_format(self):
        """Test detecting YRC format."""
        yrc_text = "[1234,567](123,45,0)嘿(234,45,0)等"
        lyrics = detect_and_parse(yrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "嘿等"

    def test_detect_char_word_format(self):
        """Test detecting char-word format."""
        lrc_text = "[00:00.00]<00:00.000>青<00:00.366>花"
        lyrics = detect_and_parse(lrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "青花"

    def test_detect_standard_lrc_format(self):
        """Test detecting standard LRC format."""
        lrc_text = "[00:01.00]Hello World\n[00:03.00]Second Line"
        lyrics = detect_and_parse(lrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].text == "Hello World"
        assert lyrics[1].text == "Second Line"

    def test_detect_empty(self):
        """Test detecting empty input."""
        assert detect_and_parse("") == []
        assert detect_and_parse(None) == []


class TestParseQrc:
    """Test parsing QRC (QQ Music word-by-word) lyrics format."""

    def test_parse_basic_qrc(self):
        """Test parsing basic QRC format."""
        # QRC format: [line_time_ms,line_dur_ms]char(offset_ms,dur_ms)char(offset_ms,dur_ms)...
        qrc_text = "[0,5000]稻(0,500)香(500,500)"

        lyrics = parse_qrc(qrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].time == 0.0
        assert lyrics[0].duration == 5.0
        assert lyrics[0].text == "稻香"
        assert len(lyrics[0].words) == 2

        # First word: absolute time 0ms
        assert lyrics[0].words[0].time == 0.0
        assert lyrics[0].words[0].duration == 0.5
        assert lyrics[0].words[0].text == "稻"

        # Second word: absolute time 500ms
        assert lyrics[0].words[1].time == 0.5
        assert lyrics[0].words[1].duration == 0.5
        assert lyrics[0].words[1].text == "香"

    def test_parse_qrc_with_xml_wrapper(self):
        """Test parsing QRC with XML wrapper."""
        qrc_text = '''<?xml version="1.0" encoding="utf-8"?>
<QrcInfos>
<QrcHeadInfo SaveTime="223" Version="100"/>
<LyricInfo LyricCount="1">
<Lyric_1 LyricType="1" LyricContent="[ti:Test Song]
[ar:Test Artist]
[0,3000]测(0,500)试(500,500)歌(1000,500)词(1500,500)
"/>
</LyricInfo>
</QrcInfos>'''

        lyrics = parse_qrc(qrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "测试歌词"
        assert len(lyrics[0].words) == 4

    def test_parse_qrc_multiple_lines(self):
        """Test parsing QRC with multiple lines."""
        qrc_text = """[0,3000]第(0,500)一(500,500)行(1000,500)
[3000,3000]第(3000,500)二(3500,500)行(4000,500)"""

        lyrics = parse_qrc(qrc_text)

        assert len(lyrics) == 2
        assert lyrics[0].time == 0.0
        assert lyrics[0].text == "第一行"
        assert lyrics[1].time == 3.0
        assert lyrics[1].text == "第二行"

    def test_parse_qrc_empty(self):
        """Test parsing empty QRC."""
        assert parse_qrc("") == []
        assert parse_qrc(None) == []

    def test_detect_qrc_format(self):
        """Test detecting QRC format."""
        qrc_text = "[0,5000]稻(0,500)香(500,500)"
        fmt = detect_format(qrc_text)
        assert fmt == 'qrc'

    def test_detect_qrc_xml_format(self):
        """Test detecting QRC XML format."""
        qrc_text = '<?xml version="1.0"?><QrcInfos><Lyric_1 LyricContent="..."/></QrcInfos>'
        fmt = detect_format(qrc_text)
        assert fmt == 'qrc'

    def test_detect_and_parse_qrc(self):
        """Test auto-detecting and parsing QRC format."""
        qrc_text = "[0,5000]稻(0,500)香(500,500)"
        lyrics = detect_and_parse(qrc_text)

        assert len(lyrics) == 1
        assert lyrics[0].text == "稻香"
