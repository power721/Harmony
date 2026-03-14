import re
import logging

logger = logging.getLogger(__name__)


# =========================
# 数据结构
# =========================

class LyricLine:

    def __init__(self, time: float, text: str, words=None):

        self.time = time
        self.text = text

        # 逐字歌词
        self.words = words or []

    def __repr__(self):

        return f"<LyricLine {self.time:.2f} {self.text}>"



# =========================
# 正则
# =========================

TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

META_RE = re.compile(r"\[(ti|ar|al|by|offset):(.+?)\]", re.I)

WORD_RE = re.compile(r"<(\d+),(\d+),\d+>([^<]+)")

# 逐字歌词格式: [00:00.00]<00:00.000>青<00:00.366>花<00:00.732>瓷
# 格式: <分:秒.毫秒>字符
CHAR_WORD_RE = re.compile(r"<(\d+):(\d+\.\d+)>([^<]+)")



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
            content = "".join([w[2] for w in words])

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

                words.append((word['time'], duration, word['char']))

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

    words = []

    matches = WORD_RE.findall(text)

    if not matches:
        return []

    for start, dur, word in matches:

        words.append(
            (
                int(start) / 1000,
                int(dur) / 1000,
                word
            )
        )

    return words