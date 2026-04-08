from __future__ import annotations


def netease_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36"
        ),
        "Referer": "https://music.163.com/",
    }


def build_netease_image_url(url: str | None, size: str) -> str | None:
    if not url:
        return None
    if "?" in url:
        return url
    return f"{url}?param={size}"
