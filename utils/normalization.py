"""Shared value normalization helpers."""


def normalize_online_provider_id(value: object) -> str | None:
    """Normalize persisted online provider ids and collapse legacy placeholders."""
    normalized = str(value or "").strip()
    if not normalized or normalized.lower() == "online":
        return None
    return normalized
