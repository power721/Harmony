"""
AcoustID service for audio fingerprinting and metadata lookup.
"""
import logging
import re
from typing import Dict, List, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)


class AcoustIDService:
    """Service for audio fingerprinting using AcoustID."""

    # Simplified Chinese character range (CJK Unified Ideographs commonly used in Chinese)
    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

    # Common Traditional Chinese characters that have simplified equivalents
    # These are characters that only appear in Traditional Chinese, not in Simplified
    # IMPORTANT: Only include characters that are DIFFERENT from their simplified forms
    TRADITIONAL_CHARS = set(
        # High-frequency traditional-only characters
        '們個為與國這說時會來對麼開還書過動進話見經學電關點長問機當實家頭道'
        '發結裡幾聽氣愛錢頭見經學電關點長問機當國實'
        # Common traditional characters in artist names - only actual traditional chars
        '鳴麗偉傑華強龍鳳飛雲風東亞國際發達陽陰葉榮業團體場務質樂隊隊員經紀'
        '導演製作詞曲編唱片發行專輯錄音帶視聽頻道劇場藝術畫展覽獎項榮譽證書'
        # Specific traditional characters
        '鳴'  # traditional for 鸣
        '麗'  # traditional for 丽
        '偉'  # traditional for 伟
        '傑'  # traditional for 杰
        '華'  # traditional for 华
        '強'  # traditional for 强
        '龍'  # traditional for 龙
        '鳳'  # traditional for 凤
        '飛'  # traditional for 飞
        '雲'  # traditional for 云
        '風'  # traditional for 风
        '東'  # traditional for 东
        '亞'  # traditional for 亚
        '國'  # traditional for 国
        '際'  # traditional for 际
        '發'  # traditional for 发
        '達'  # traditional for 达
        '陽'  # traditional for 阳
        '陰'  # traditional for 阴
        '葉'  # traditional for 叶
        '榮'  # traditional for 荣
        '業'  # traditional for 业
        '團'  # traditional for 团
        '體'  # traditional for 体
        '場'  # traditional for 场
        '務'  # traditional for 务
        '質'  # traditional for 质
        '樂'  # traditional for 乐
        '隊'  # traditional for 队
        '員'  # traditional for 员
        '經'  # traditional for 经
        '紀'  # traditional for 纪
        '導'  # traditional for 导
        '演'  # traditional for 演
        '製'  # traditional for 制
        '詞'  # traditional for 词
        '編'  # traditional for 编
        '專'  # traditional for 专
        '輯'  # traditional for 辑
        '錄'  # traditional for 录
        '帶'  # traditional for 带
        '視'  # traditional for 视
        '聽'  # traditional for 听
        '頻'  # traditional for 频
        '劇'  # traditional for 剧
        '藝'  # traditional for 艺
        '術'  # traditional for 术
        '畫'  # traditional for 画
        '覽'  # traditional for 览
        '獎'  # traditional for 奖
        '項'  # traditional for 项
        '譽'  # traditional for 誉
        '證'  # traditional for 证
        '書'  # traditional for 书
        '關'  # traditional for 关
        '長'  # traditional for 长
        '問'  # traditional for 问
        '實'  # traditional for 实
        '頭'  # traditional for 头
        '結'  # traditional for 结
        '裡'  # traditional for 里
        '幾'  # traditional for 几
        '氣'  # traditional for 气
        '愛'  # traditional for 爱
        '錢'  # traditional for 钱
        '們'  # traditional for 们
        '個'  # traditional for 个
        '為'  # traditional for 为
        '與'  # traditional for 与
        '這'  # traditional for 这
        '說'  # traditional for 说
        '時'  # traditional for 时
        '會'  # traditional for 会
        '來'  # traditional for 来
        '對'  # traditional for 对
        '麼'  # traditional for 么
        '開'  # traditional for 开
        '還'  # traditional for 还
        '過'  # traditional for 过
        '動'  # traditional for 动
        '進'  # traditional for 进
        '話'  # traditional for 话
        '見'  # traditional for 见
    )

    @classmethod
    def _contains_chinese(cls, text: str) -> bool:
        """Check if text contains Chinese characters."""
        if not text:
            return False
        return bool(cls.CHINESE_PATTERN.search(text))

    @classmethod
    def _has_traditional_chars(cls, text: str) -> bool:
        """Check if text contains traditional Chinese characters."""
        if not text:
            return False
        return any(char in cls.TRADITIONAL_CHARS for char in text)

    @classmethod
    def _chinese_score(cls, text: str) -> float:
        """
        Calculate a score for Chinese preference.
        Higher score = more preferred (simplified Chinese).
        Returns negative for non-Chinese text.
        """
        if not text or not cls._contains_chinese(text):
            return -1.0

        # Check for traditional characters (lower score)
        if cls._has_traditional_chars(text):
            return 0.5  # Traditional Chinese

        return 1.0  # Simplified Chinese

    @classmethod
    def identify_track(
        cls,
        file_path: str,
        api_key: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Identify a track using AcoustID fingerprinting.

        Args:
            file_path: Path to the audio file
            api_key: AcoustID API key

        Returns:
            List of match results with score, title, artist, album, etc.
            or None on failure
        """
        try:
            import acoustid

            results = []
            for score, recording_id, title, artist in acoustid.match(api_key, file_path):
                result = {
                    'score': score,
                    'recording_id': recording_id,
                    'title': title or '',
                    'artist': artist or '',
                }
                results.append(result)
                logger.debug(f"AcoustID match: score={score:.2f}, title={title}, artist={artist}")

            if results:
                logger.info(f"AcoustID found {len(results)} matches for {file_path}")
                return results
            else:
                logger.info(f"AcoustID found no matches for {file_path}")
                return []

        except ImportError:
            logger.error("pyacoustid package not installed. Run: pip install pyacoustid")
            return None
        except Exception as e:
            logger.error(f"AcoustID identification failed: {e}", exc_info=True)
            return None

    @classmethod
    def get_best_match(cls, results: List[Dict[str, Any]], prefer_chinese: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get the best match from AcoustID results.

        Args:
            results: List of match results from identify_track
            prefer_chinese: If True, prefer results with Chinese characters (simplified preferred)

        Returns:
            Best match dict with score, title, artist, or None if no good match
        """
        if not results:
            return None

        # Filter results with reasonable score and title
        valid_results = [r for r in results if r.get('score', 0) >= 0.5 and r.get('title')]
        if not valid_results:
            return None

        if prefer_chinese:
            # Score each result based on Chinese preference
            scored_results = []
            for r in valid_results:
                title = r.get('title', '')
                artist = r.get('artist', '')

                # Calculate Chinese score (simplified = 1.0, traditional = 0.5, non-Chinese = -1.0)
                title_cn_score = cls._chinese_score(title)
                artist_cn_score = cls._chinese_score(artist)

                # Use min() to ensure traditional chars in any field lower the overall score
                # This ensures simplified Chinese is preferred when both exist
                cn_score = min(title_cn_score, artist_cn_score)

                # Total score: Chinese preference * 10 + AcoustID score
                # This ensures Chinese results are preferred, but within same category, higher match score wins
                total_score = cn_score * 10 + r.get('score', 0)
                scored_results.append((r, total_score, cn_score))
                logger.debug(f"Result score: title={title}, artist={artist}, cn_score={cn_score}, total={total_score:.2f}")

            # Sort by total score (descending)
            scored_results.sort(key=lambda x: x[1], reverse=True)
            best = scored_results[0][0]
            best_cn_score = scored_results[0][2]

            # Only use Chinese preference if we found a Chinese result
            if best_cn_score > 0:
                logger.debug(f"Selected Chinese result: title={best.get('title')}, artist={best.get('artist')}")
                return best

        # Fall back to highest score result
        sorted_results = sorted(valid_results, key=lambda x: x.get('score', 0), reverse=True)
        return sorted_results[0]

    @classmethod
    def enhance_track(
        cls,
        file_path: str,
        api_key: str,
        current_metadata: Optional[Dict[str, Any]] = None,
        update_file: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Enhance metadata for a track using AcoustID.

        Args:
            file_path: Path to the audio file
            api_key: AcoustID API key
            current_metadata: Current metadata to merge with
            update_file: Whether to update the audio file metadata

        Returns:
            Enhanced metadata dict or None on failure
        """
        if current_metadata is None:
            current_metadata = {}

        results = cls.identify_track(file_path, api_key)
        if not results:
            return None

        best = cls.get_best_match(results)
        if not best:
            return None

        # Build enhanced metadata
        enhanced = {
            'title': best.get('title', current_metadata.get('title', '')),
            'artist': best.get('artist', current_metadata.get('artist', '')),
            'album': current_metadata.get('album', ''),  # AcoustID doesn't always provide album
            'duration': current_metadata.get('duration', 0),
            'cover': current_metadata.get('cover'),
            'score': best.get('score', 0),
        }

        # Update file metadata if requested
        if update_file:
            try:
                from services.metadata.metadata_service import MetadataService
                MetadataService.save_metadata(
                    file_path,
                    title=enhanced['title'],
                    artist=enhanced['artist'],
                    album=enhanced['album']
                )
                logger.info(f"Updated file metadata for {file_path}")
            except Exception as e:
                logger.error(f"Failed to update file metadata: {e}", exc_info=True)

        return enhanced
