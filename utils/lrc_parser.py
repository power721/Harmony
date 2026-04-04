import logging
import re
import bisect
from functools import lru_cache
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# =========================
# 数据结构
# =========================

@dataclass
class LyricWord:
    """逐字歌词的单字数据"""
    time: float       # 开始时间(秒)
    duration: float   # 持续时间(秒)
    text: str         # 字符内容

    def __repr__(self):
        return f"<{self.text}@{self.time:.2f}s>"


class LyricLine:

    def __init__(self, time: float, text: str, words=None, duration: float = 0):
        self.time = time
        self.text = text
        self.words: List[LyricWord] = words or []
        self.duration = duration
        self.end = time + duration if duration else 0

    def __repr__(self):
        return f"<LyricLine {self.time:.2f}s {self.text}>"


# =========================
# 正则
# =========================

TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
META_RE = re.compile(r"\[(ti|ar|al|by|offset):(.+?)\]", re.I)

WORD_RE = re.compile(r"<(\d+),(\d+),\d+>([^<]+)")
CHAR_WORD_RE = re.compile(r"<(\d+):(\d+\.\d+)>([^<]+)")

YRC_LINE_RE = re.compile(r"\[(\d+),(\d+)\]")
YRC_WORD_RE = re.compile(r"\((\d+),(\d+),\d+\)([^(]+)")

QRC_LINE_RE = re.compile(r"\[(\d+),(\d+)\]")
QRC_WORD_RE = re.compile(r"(.*?)\((\d+),(\d+)\)")
QRC_XML_RE = re.compile(r"<QrcInfos>")


# =========================
# 工具函数
# =========================

def ms_to_s(ms: int) -> float:
    return ms / 1000.0


# =========================
# XML 解析
# =========================


def extract_qrc_xml(text: str) -> str:
    """
    专门解析 QQ 音乐 QRC XML（兼容非法 XML）
    """

    import re
    import html

    # 🔥 关键：DOTALL + 非贪婪
    m = re.search(r'LyricContent="(.*?)"', text, re.DOTALL)

    if not m:
        return ""

    content = m.group(1)

    # HTML 反转义
    content = html.unescape(content)

    return content


# =========================
# LRC
# =========================

def parse_lrc(text: str) -> List[LyricLine]:
    lyrics = []

    if CHAR_WORD_RE.search(text):
        return parse_char_word_lrc(text)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if META_RE.match(line):
            continue

        times = TIME_RE.findall(line)
        if not times:
            continue

        content = TIME_RE.sub("", line).strip() or " "

        words = parse_words(content)
        if words:
            content = "".join(w.text for w in words)

        for m, s in times:
            t = int(m) * 60 + float(s)
            lyrics.append(LyricLine(t, content, words))

    lyrics.sort(key=lambda x: x.time)
    fix_durations(lyrics)
    return lyrics


# =========================
# CHAR WORD LRC
# =========================

def parse_char_word_lrc(text: str) -> List[LyricLine]:
    lyrics = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        line = TIME_RE.sub("", line)

        chars = []
        for m in CHAR_WORD_RE.finditer(line):
            t = int(m.group(1)) * 60 + float(m.group(2))
            chars.append((t, m.group(3)))

        if not chars:
            continue

        words = []
        for i, (t, ch) in enumerate(chars):
            dur = chars[i + 1][0] - t if i < len(chars) - 1 else 1.0
            words.append(LyricWord(t, dur, ch))

        lyrics.append(LyricLine(chars[0][0], "".join(c[1] for c in chars), words))

    lyrics.sort(key=lambda x: x.time)
    fix_durations(lyrics)
    return lyrics


# =========================
# 普通逐字
# =========================

def parse_words(text: str):
    words = []
    for s, d, w in WORD_RE.findall(text):
        words.append(LyricWord(int(s)/1000, int(d)/1000, w))
    return words


# =========================
# YRC
# =========================

def parse_yrc(text: str) -> List[LyricLine]:
    if not text:
        return []

    lyrics = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = YRC_LINE_RE.match(line)
        if not m:
            continue

        line_time = int(m.group(1))
        line_dur = int(m.group(2))

        content = line[m.end():]

        words = []
        full = []

        for wm in YRC_WORD_RE.finditer(content):
            offset = int(wm.group(1))
            dur = int(wm.group(2))
            ch = wm.group(3)

            # ✅ 防御式
            t = offset if offset > line_dur else line_time + offset

            words.append(LyricWord(ms_to_s(t), ms_to_s(dur), ch))
            full.append(ch)

        if words:
            lyrics.append(LyricLine(ms_to_s(line_time), "".join(full), words, ms_to_s(line_dur)))

    lyrics.sort(key=lambda x: x.time)
    fix_durations(lyrics)
    return lyrics


# =========================
# QRC（重点修复）
# =========================

def parse_qrc(text: str) -> List[LyricLine]:
    if not text:
        return []

    if "<QrcInfos>" in text:
        text = extract_qrc_xml(text)

    lyrics = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = QRC_LINE_RE.match(line)
        if not m:
            continue

        line_time = int(m.group(1))
        line_dur = int(m.group(2))

        content = line[m.end():]

        words = []
        full = []

        for wm in QRC_WORD_RE.finditer(content):
            ch = wm.group(1)
            offset = int(wm.group(2))
            dur = int(wm.group(3))

            if ch == "":
                continue

            words.append(LyricWord(ms_to_s(offset), ms_to_s(dur), ch))
            full.append(ch)

        if words:
            lyrics.append(LyricLine(
                ms_to_s(line_time),
                "".join(full),
                words,
                ms_to_s(line_dur)
            ))

    lyrics.sort(key=lambda x: x.time)
    fix_durations(lyrics)
    return lyrics


# =========================
# duration 修复（关键）
# =========================

def fix_durations(lines: List[LyricLine]):

    for i, line in enumerate(lines):

        if line.duration:
            end = line.time + line.duration
        elif i < len(lines) - 1:
            end = lines[i + 1].time
        else:
            end = line.time + 3

        line.end = end

        for j, w in enumerate(line.words):
            if j < len(line.words) - 1:
                w.duration = line.words[j+1].time - w.time
            else:
                w.duration = max(0, end - w.time)


def _clone_lines(lines: List[LyricLine]) -> List[LyricLine]:
    """Return a deep-enough copy for consumers to mutate independently."""
    cloned_lines: List[LyricLine] = []
    for line in lines:
        cloned_words = [
            LyricWord(word.time, word.duration, word.text)
            for word in line.words
        ]
        cloned_line = LyricLine(line.time, line.text, cloned_words, line.duration)
        cloned_line.end = line.end
        cloned_lines.append(cloned_line)
    return cloned_lines


@lru_cache(maxsize=128)
def _detect_and_parse_cached(text: str) -> tuple[LyricLine, ...]:
    """Parse lyrics text once and reuse the parsed result across widgets."""
    if "<QrcInfos>" in text:
        logger.info("[lrc_parser] 检测到 QRC XML 格式，使用 QRC 解析器")
        lines = parse_qrc(text)
    elif QRC_WORD_RE.search(text) and not YRC_WORD_RE.search(text):
        logger.info("[lrc_parser] 检测到 QRC 格式，使用 QRC 解析器")
        lines = parse_qrc(text)
    elif YRC_WORD_RE.search(text):
        logger.info("[lrc_parser] 检测到 YRC 格式，使用 YRC 解析器")
        lines = parse_yrc(text)
    elif CHAR_WORD_RE.search(text):
        logger.info("CHAR")
        lines = parse_char_word_lrc(text)
    else:
        lines = parse_lrc(text)
    return tuple(lines)


# =========================
# 检测入口（修复优先级）
# =========================

def detect_and_parse(text: str) -> List[LyricLine]:

    if not text:
        return []
    return _clone_lines(list(_detect_and_parse_cached(text)))


# =========================
# 高性能查询（播放器用）
# =========================

def build_word_index(lines: List[LyricLine]) -> List[LyricWord]:
    return sorted([w for l in lines for w in l.words], key=lambda w: w.time)


def find_current_word(words: List[LyricWord], t: float) -> Optional[LyricWord]:
    times = [w.time for w in words]
    i = bisect.bisect_right(times, t) - 1
    if i >= 0:
        w = words[i]
        if w.time <= t <= w.time + w.duration:
            return w
    return None


def find_current_line(lines: List[LyricLine], t: float) -> Optional[LyricLine]:
    """Find the current lyric line using binary search (O(log n))."""
    if not lines:
        return None

    # Binary search for the line that contains time t
    times = [line.time for line in lines]
    i = bisect.bisect_right(times, t) - 1

    if i >= 0:
        line = lines[i]
        if line.time <= t <= line.end:
            return line
    return None

def detect_format(text: str) -> str:
    """
    检测歌词格式类型。

    返回:
        'qrc' | 'yrc' | 'lrc' | 'char' | 'unknown'
    """
    if not text:
        return "unknown"

    text = text.strip()

    # =========================
    # 1. QRC XML（最高优先级）
    # =========================
    if "<QrcInfos>" in text:
        return "qrc"

    # =========================
    # 2. YRC（网易云）
    # 特征：(offset,duration,flag)字
    # =========================
    if YRC_WORD_RE.search(text):
        return "yrc"

    # =========================
    # 3. QRC（QQ音乐）
    # 特征：字(offset,duration)
    # ⚠️ 必须排除 YRC
    # =========================
    if QRC_WORD_RE.search(text):
        return "qrc"

    # =========================
    # 4. CHAR WORD（逐字绝对时间）
    # =========================
    if CHAR_WORD_RE.search(text):
        return "char"

    # =========================
    # 5. 标准 LRC
    # =========================
    if TIME_RE.search(text):
        return "lrc"

    return "unknown"
