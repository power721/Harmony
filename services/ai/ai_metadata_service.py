"""
AI Metadata Service for enhancing music metadata using AI models.
"""
import json
import logging
from typing import Dict, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

METADATA_PROMPT_TEMPLATE = """You are a music metadata parser specialized in Chinese music.

Extract the following fields from the music filename:
- artist
- title
- album

Rules:
1. Ignore file extension
2. Handle Chinese and English names
3. Normalize artist names (e.g., "Taylor Swift" not "taylor swift")
4. If album is not present, return null
5. Return JSON only, no explanation

Filename: {filename}"""

BATCH_METADATA_PROMPT_TEMPLATE = """You are a music metadata parser specialized in Chinese music.

Extract metadata from the following music filenames.
Return a JSON array where each item contains:
- index: the original index number (0-based)
- artist: artist name (normalized, e.g., "Taylor Swift" not "taylor swift")
- title: song title
- album: album name (null if not present in filename)

Rules:
1. Ignore file extensions
2. Handle Chinese and English names
3. Normalize artist names
4. Return JSON array only, no explanation

Filenames (one per line with index):
{filenames}"""


class AIMetadataService:
    """Service for enhancing music metadata using AI models."""

    @classmethod
    def enhance_metadata(
            cls,
            filename: str,
            base_url: str,
            api_key: str,
            model: str,
            current_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Enhance metadata using AI model.

        Args:
            filename: The music filename (without path)
            base_url: AI API base URL
            api_key: AI API key
            model: AI model name
            current_metadata: Current metadata to check for completeness

        Returns:
            Dictionary with 'title', 'artist', 'album' keys, or None on failure
        """
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            prompt = METADATA_PROMPT_TEMPLATE.format(filename=filename)

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )

            if not response.choices:
                logger.warning("AI returned empty response")
                return None

            content = response.choices[0].message.content.strip()

            # Try to extract JSON from response
            result = cls._parse_json_response(content)
            if result:
                logger.info(f"AI enhanced metadata for {filename}: {result}")
                return result

            logger.warning(f"Failed to parse AI response: {content}")
            return None

        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            return None
        except Exception as e:
            logger.error(f"AI metadata enhancement failed: {e}", exc_info=True)
            return None

    @classmethod
    def _parse_json_response(cls, content: str) -> Optional[Dict[str, str]]:
        """
        Parse JSON response from AI.

        Args:
            content: Raw response content

        Returns:
            Parsed metadata dict or None
        """
        try:
            # Try direct JSON parse
            result = json.loads(content)
            return cls._validate_metadata(result)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response (handle markdown code blocks)
        import re

        # Look for JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return cls._validate_metadata(result)
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in the text
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return cls._validate_metadata(result)
            except json.JSONDecodeError:
                pass

        return None

    @classmethod
    def _validate_metadata(cls, data: dict) -> Optional[Dict[str, str]]:
        """
        Validate and clean metadata from AI response.

        Args:
            data: Parsed JSON data

        Returns:
            Cleaned metadata dict or None if invalid
        """
        if not isinstance(data, dict):
            return None

        result = {}

        # Extract and clean fields
        for field in ['title', 'artist', 'album']:
            value = data.get(field)
            if value is not None and value != "null":
                if isinstance(value, str):
                    cleaned = value.strip()
                    if cleaned and cleaned.lower() != "null":
                        result[field] = cleaned

        # Must have at least title
        if 'title' not in result:
            return None

        return result

    @classmethod
    def is_metadata_incomplete(cls, metadata: Dict[str, Any]) -> bool:
        """
        Check if metadata is incomplete and needs enhancement.

        Args:
            metadata: Current metadata dict

        Returns:
            True if metadata is incomplete
        """
        title = metadata.get('title', '')
        artist = metadata.get('artist', '')

        # Consider incomplete if title is just filename or artist is missing
        if not title:
            return True

        # Check if title looks like a filename (has extension)
        title_lower = title.lower()
        if any(title_lower.endswith(ext) for ext in ['.mp3', '.flac', '.ogg', '.m4a', '.wav']):
            return True

        # Artist is empty
        if not artist:
            return True

        return False

    @classmethod
    def enhance_track(
            cls,
            file_path: str,
            base_url: str,
            api_key: str,
            model: str,
            current_metadata: Dict[str, Any],
            update_file: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Enhance metadata for a single track.

        Args:
            file_path: Path to the audio file
            base_url: AI API base URL
            api_key: AI API key
            model: AI model name
            current_metadata: Current metadata from file
            update_file: Whether to update the audio file metadata

        Returns:
            Enhanced metadata dict or None on failure
        """
        from pathlib import Path

        filename = Path(file_path).name

        # Get enhanced metadata from AI
        enhanced = cls.enhance_metadata(
            filename=filename,
            base_url=base_url,
            api_key=api_key,
            model=model,
            current_metadata=current_metadata
        )

        if not enhanced:
            return None

        # Merge with current metadata (prefer AI for title/artist, keep current for duration/cover)
        result = {
            'title': enhanced.get('title', current_metadata.get('title', '')),
            'artist': enhanced.get('artist', current_metadata.get('artist', '')),
            'album': enhanced.get('album', current_metadata.get('album', '')),
            'duration': current_metadata.get('duration', 0),
            'cover': current_metadata.get('cover'),
        }

        # Update file metadata if requested
        if update_file:
            try:
                from services.metadata.metadata_service import MetadataService
                MetadataService.save_metadata(
                    file_path,
                    title=result['title'],
                    artist=result['artist'],
                    album=result['album']
                )
                logger.info(f"Updated file metadata for {file_path}")
            except Exception as e:
                logger.error(f"Failed to update file metadata: {e}", exc_info=True)

        return result

    @classmethod
    def enhance_metadata_batch(
            cls,
            filenames: list,
            base_url: str,
            api_key: str,
            model: str,
    ) -> Dict[int, Dict[str, str]]:
        """
        Batch enhance metadata using AI model.

        Args:
            filenames: List of music filenames (without path)
            base_url: AI API base URL
            api_key: AI API key
            model: AI model name

        Returns:
            Dict mapping index to metadata dict
        """
        if not filenames:
            return {}

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            # Format filenames with index
            indexed_filenames = "\n".join(
                f"[{i}] {name}" for i, name in enumerate(filenames)
            )
            prompt = BATCH_METADATA_PROMPT_TEMPLATE.format(filenames=indexed_filenames)

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )

            if not response.choices:
                logger.warning("AI returned empty response for batch")
                return {}

            content = response.choices[0].message.content.strip()
            results = cls._parse_batch_json_response(content)

            if results:
                logger.info(f"AI enhanced {len(results)} tracks in batch")

            return results

        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            return {}
        except Exception as e:
            logger.error(f"AI batch metadata enhancement failed: {e}", exc_info=True)
            return {}

    @classmethod
    def _parse_batch_json_response(cls, content: str) -> Dict[int, Dict[str, str]]:
        """
        Parse batch JSON response from AI.

        Args:
            content: Raw response content

        Returns:
            Dict mapping index to metadata dict
        """
        import re

        results = {}

        # Try to extract JSON array from response
        json_data = None

        # Try direct JSON parse
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from code blocks
        if json_data is None:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    json_data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        # Try to find JSON array in the text
        if json_data is None:
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                try:
                    json_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not isinstance(json_data, list):
            logger.warning(f"Expected JSON array, got: {type(json_data)}")
            return {}

        # Parse each item
        for item in json_data:
            if not isinstance(item, dict):
                continue

            index = item.get('index')
            if index is None:
                continue

            # Validate metadata
            metadata = cls._validate_metadata(item)
            if metadata:
                results[index] = metadata

        return results
