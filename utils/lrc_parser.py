import logging
import re
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
    """歌词行数据"""

    def __init__(self, time: float, text: str, words: List[LyricWord] = None, duration: float = 0):
        self.time = time           # 行开始时间(秒)
        self.text = text           # 行文本
        self.words = words or []   # 逐字歌词列表
        self.duration = duration   # 行持续时间(秒)

    def __repr__(self):
        return f"<LyricLine {self.time:.2f}s {self.text}>"


# =========================
# 正则
# =========================

TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

META_RE = re.compile(r"\[(ti|ar|al|by|offset):(.+?)\]", re.I)

WORD_RE = re.compile(r"<(\d+),(\d+),\d+>([^<]+)")

# 逐字歌词格式: [00:00.00]<00:00.000>青<00:00.366>花<00:00.732>瓷
# 格式: <分:秒.毫秒>字符
CHAR_WORD_RE = re.compile(r"<(\d+):(\d+\.\d+)>([^<]+)")

# YRC 逐字歌词格式 (网易云)
# 格式: [行开始时间ms,行持续时间ms](字偏移ms,字持续时间ms,flag)字
YRC_LINE_RE = re.compile(r"\[(\d+),(\d+)\]")
YRC_WORD_RE = re.compile(r"\((\d+),(\d+),\d+\)([^(]+)")

# QRC 逐字歌词格式 (QQ音乐)
# 格式: [行开始时间ms,行持续时间ms]字(绝对偏移ms,字持续时间ms)字(绝对偏移ms,字持续时间ms)...
# 注意：QRC的偏移是绝对时间(相对于歌曲开始)，不是相对于行开始
QRC_LINE_RE = re.compile(r"\[(\d+),(\d+)\]")
QRC_WORD_RE = re.compile(r"([^\(\[\]]+)\((\d+),(\d+)\)")

# QRC XML 包装检测
QRC_XML_RE = re.compile(r"<QrcInfos>")


# =========================
# LRC 解析
# =========================

def parse_lrc(text: str):
    lyrics = []

    meta = {}

    # 检测是否是逐字歌词格式
    is_char_word_format = bool(CHAR_WORD_RE.search(text))

    if is_char_word_format:
        logger.info("[lrc_parser] 检测到逐字歌词格式，使用专用解析器")
        return parse_char_word_lrc(text)

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        # metadata
        meta_match = META_RE.match(line)

        if meta_match:
            key = meta_match.group(1).lower()
            val = meta_match.group(2).strip()

            meta[key] = val

            continue

        times = TIME_RE.findall(line)

        if not times:
            continue

        # 去掉时间标签
        content = TIME_RE.sub("", line).strip()

        if not content:
            content = " "

        # 逐字解析
        words = parse_words(content)

        # 去掉逐字标签后的文本
        if words:
            content = "".join([w.text for w in words])

        for m, s in times:
            t = int(m) * 60 + float(s)

            lyrics.append(
                LyricLine(
                    time=t,
                    text=content,
                    words=words
                )
            )

    lyrics.sort(key=lambda x: x.time)

    return lyrics


# =========================
# 逐字歌词解析
# =========================

def parse_char_word_lrc(text: str):
    """
    解析逐字歌词格式: [00:00.00]<00:00.000>青<00:00.366>花<00:00.732>瓷

    注意：<00:00.000> 是绝对时间，不是偏移量

    Args:
        text: 逐字歌词文本

    Returns:
        List[LyricLine]: 解析后的歌词行列表
    """
    lyrics = []
    meta = {}

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        # 解析元数据
        meta_match = META_RE.match(line)
        if meta_match:
            key = meta_match.group(1).lower()
            val = meta_match.group(2).strip()
            meta[key] = val
            continue

        # 提取行起始时间 [00:00.00]（可选，有些格式可能没有）
        line_time_match = TIME_RE.match(line)

        # 去掉行起始时间标签（如果存在）
        if line_time_match:
            content = line[line_time_match.end():]
        else:
            content = line

        # 解析逐字时间标签 <00:00.000>字符
        char_words = []

        for match in CHAR_WORD_RE.finditer(content):
            char_minutes = int(match.group(1))
            char_seconds = float(match.group(2))
            char = match.group(3)

            # <00:00.000> 格式就是绝对时间
            char_time = char_minutes * 60 + char_seconds

            char_words.append({
                'time': char_time,
                'char': char
            })

        if char_words:
            # 生成完整的行文本
            full_text = ''.join([w['char'] for w in char_words])

            # 计算每个字符的持续时间
            words = []
            for i, word in enumerate(char_words):
                if i < len(char_words) - 1:
                    # 不是最后一个字符，持续时间到下一个字符
                    duration = char_words[i + 1]['time'] - word['time']
                else:
                    # 最后一个字符，默认持续1秒
                    duration = 1.0

                words.append(LyricWord(
                    time=word['time'],
                    duration=duration,
                    text=word['char']
                ))

            # 使用第一个字符的时间作为行时间
            first_char_time = char_words[0]['time']

            lyrics.append(
                LyricLine(
                    time=first_char_time,
                    text=full_text,
                    words=words
                )
            )

    lyrics.sort(key=lambda x: x.time)

    return lyrics


# =========================
# 逐字解析
# =========================

def parse_words(text):
    """解析 <start,dur,flag>word 格式的逐字歌词"""
    words = []

    matches = WORD_RE.findall(text)

    if not matches:
        return []

    for start, dur, word in matches:
        words.append(
            LyricWord(
                time=int(start) / 1000,
                duration=int(dur) / 1000,
                text=word
            )
        )

    return words

def parse_yrc(yrc_text: str) -> List[LyricLine]:

    if not yrc_text:
        return []

    lyrics = []

    for line in yrc_text.splitlines():
        line = line.strip()
        if not line:
            continue

        line_match = YRC_LINE_RE.match(line)
        if not line_match:
            continue

        line_time_ms = int(line_match.group(1))
        line_duration_ms = int(line_match.group(2))

        content = line[line_match.end():]

        words = []
        full_text_parts = []

        for word_match in YRC_WORD_RE.finditer(content):

            offset_ms = int(word_match.group(1))
            duration_ms = int(word_match.group(2))
            char = word_match.group(3)

            # =========================
            # 关键修复
            # =========================

            # 判断是否是绝对时间
            if offset_ms >= line_time_ms:
                word_time_ms = offset_ms
            else:
                word_time_ms = line_time_ms + offset_ms

            words.append(LyricWord(
                time=word_time_ms / 1000,
                duration=duration_ms / 1000,
                text=char
            ))

            full_text_parts.append(char)

        if words:
            lyrics.append(LyricLine(
                time=line_time_ms / 1000,
                text=''.join(full_text_parts),
                words=words,
                duration=line_duration_ms / 1000
            ))

    lyrics.sort(key=lambda x: x.time)

    return lyrics


def parse_qrc(qrc_text: str) -> List[LyricLine]:
    """
    解析 QQ音乐 QRC 格式歌词。

    QRC 格式特点：
    - 可能有 XML 包装: <QrcInfos>...<Lyric_1 LyricContent="..."/>
    - 行格式: [行开始时间ms,行持续时间ms]字(绝对偏移ms,持续时间ms)字(绝对偏移ms,持续时间ms)...
    - 偏移是绝对时间(相对于歌曲开始)，不是相对于行开始

    Args:
        qrc_text: QRC 格式歌词文本

    Returns:
        List[LyricLine]: 解析后的歌词行列表
    """
    if not qrc_text:
        return []

    # 如果有 XML 包装，提取 LyricContent
    if '<QrcInfos>' in qrc_text:
        import re as _re
        # 提取 LyricContent 属性值
        content_match = _re.search(r'LyricContent="([^"]*)"', qrc_text)
        if content_match:
            # 处理转义字符
            qrc_text = content_match.group(1)
            # 替换 XML 实体
            qrc_text = qrc_text.replace('&lt;', '<').replace('&gt;', '>')
            qrc_text = qrc_text.replace('&amp;', '&').replace('&quot;', '"')
            qrc_text = qrc_text.replace('&#10;', '\n').replace('&#13;', '\r')

    lyrics = []

    for line in qrc_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # 解析元数据
        meta_match = META_RE.match(line)
        if meta_match:
            continue

        # 匹配行头 [开始时间ms,持续时间ms]
        line_match = QRC_LINE_RE.match(line)
        if not line_match:
            continue

        line_time_ms = int(line_match.group(1))
        line_duration_ms = int(line_match.group(2))

        content = line[line_match.end():]

        words = []
        full_text_parts = []

        # 解析每个字: 字(绝对偏移ms,持续时间ms)
        for word_match in QRC_WORD_RE.finditer(content):
            char = word_match.group(1)
            offset_ms = int(word_match.group(2))
            duration_ms = int(word_match.group(3))

            # QRC 的偏移是绝对时间
            word_time_ms = offset_ms

            words.append(LyricWord(
                time=word_time_ms / 1000,
                duration=duration_ms / 1000,
                text=char
            ))

            full_text_parts.append(char)

        if words:
            lyrics.append(LyricLine(
                time=line_time_ms / 1000,
                text=''.join(full_text_parts),
                words=words,
                duration=line_duration_ms / 1000
            ))

    lyrics.sort(key=lambda x: x.time)

    return lyrics

def detect_and_parse(text: str) -> List[LyricLine]:
    """
    自动检测歌词格式并解析。

    支持的格式:
    - QRC (QQ音乐逐字歌词): XML包装或 [时间,时长]字(偏移,时长)格式
    - YRC (网易云逐字歌词): [时间,时长](偏移,时长,flag)字
    - 逐字格式: [00:00.00]<00:00.000>字
    - 标准 LRC: [00:00.00]歌词

    Args:
        text: 歌词文本

    Returns:
        List[LyricLine]: 解析后的歌词行列表
    """
    if not text:
        return []

    # 检测 QRC 格式 (QQ音乐): XML包装或 [数字,数字]字(数字,数字)格式
    if QRC_XML_RE.search(text) or (QRC_LINE_RE.search(text) and QRC_WORD_RE.search(text) and '(' in text and ')' in text and '<QrcInfos>' not in text):
        # 如果有XML包装或者符合QRC格式(字在前，括号在后)
        if QRC_XML_RE.search(text) or (QRC_LINE_RE.search(text) and QRC_WORD_RE.search(text)):
            # 检查是否是QRC格式：字(偏移,时长) 而不是 (偏移,时长,flag)字
            if QRC_XML_RE.search(text) or not YRC_WORD_RE.search(text):
                logger.info("[lrc_parser] 检测到 QRC 格式，使用 QRC 解析器")
                return parse_qrc(text)

    # 检测 YRC 格式: [数字,数字](数字,数字,数字)
    if YRC_LINE_RE.search(text) and YRC_WORD_RE.search(text):
        logger.info("[lrc_parser] 检测到 YRC 格式，使用 YRC 解析器")
        return parse_yrc(text)

    # 使用原有的 parse_lrc 函数处理其他格式
    return parse_lrc(text)


def detect_format(text: str) -> str:
    """
    检测歌词格式类型。

    Returns:
        str: 'qrc', 'yrc', 'lrc', 或 'unknown'
    """
    if not text:
        return 'unknown'

    # 检测 QRC 格式
    if QRC_XML_RE.search(text):
        return 'qrc'

    if QRC_LINE_RE.search(text) and QRC_WORD_RE.search(text):
        # 检查是否是QRC格式：字(偏移,时长) 而不是 (偏移,时长,flag)字
        if not YRC_WORD_RE.search(text):
            return 'qrc'

    # 检测 YRC 格式
    if YRC_LINE_RE.search(text) and YRC_WORD_RE.search(text):
        return 'yrc'

    # 检测标准 LRC 格式
    if TIME_RE.search(text):
        return 'lrc'

    return 'unknown'
