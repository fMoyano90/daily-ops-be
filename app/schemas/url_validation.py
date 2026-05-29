from typing import Optional
from urllib.parse import urlsplit


ALLOWED_EXTERNAL_URL_SCHEMES = {"http", "https"}


def normalize_external_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    if any(char in cleaned for char in ("\r", "\n", "\t")):
        raise ValueError("external_url must be a valid http(s) URL")

    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in ALLOWED_EXTERNAL_URL_SCHEMES or not parsed.netloc:
        raise ValueError("external_url must be a valid http(s) URL")

    return cleaned
