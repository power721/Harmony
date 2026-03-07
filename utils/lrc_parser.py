import re


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



# =========================
# LRC 解析
# =========================

def parse_lrc(text: str):

    lyrics = []

    meta = {}

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