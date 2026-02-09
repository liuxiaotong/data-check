"""Text quality detection rules for LLM data."""

import re
from collections import Counter
from typing import Any, Dict, Set


# --- N-gram helpers (for near-duplicate detection) ---


def compute_ngrams(text: str, n: int = 3) -> Set[str]:
    """Compute character n-grams from text."""
    text = text.lower().strip()
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return len(set_a & set_b) / union


# --- Language detection ---

# Unicode ranges for language detection
_LANG_RANGES = [
    ("zh", re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")),       # Chinese
    ("ja", re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")),       # Japanese (Hiragana + Katakana)
    ("ko", re.compile(r"[\uac00-\ud7af\u1100-\u11ff]")),       # Korean
    ("ar", re.compile(r"[\u0600-\u06ff\u0750-\u077f]")),       # Arabic
    ("ru", re.compile(r"[\u0400-\u04ff]")),                     # Cyrillic
    ("th", re.compile(r"[\u0e00-\u0e7f]")),                     # Thai
]


def detect_language(text: str) -> tuple:
    """Detect the dominant language of a text based on Unicode character ranges.

    Returns:
        (language_code, confidence) tuple. Language codes:
        'zh', 'ja', 'ko', 'ar', 'ru', 'th', 'latin', 'unknown'
    """
    if not text or len(text.strip()) < 3:
        return ("unknown", 0.0)

    total_alpha = 0
    lang_counts: Dict[str, int] = {}

    for lang, pattern in _LANG_RANGES:
        count = len(pattern.findall(text))
        if count > 0:
            lang_counts[lang] = count
            total_alpha += count

    # Count Latin characters
    latin_count = len(re.findall(r"[a-zA-Z]", text))
    if latin_count > 0:
        lang_counts["latin"] = latin_count
        total_alpha += latin_count

    if total_alpha == 0:
        return ("unknown", 0.0)

    # Find dominant language
    dominant = max(lang_counts, key=lang_counts.get)
    confidence = lang_counts[dominant] / total_alpha

    return (dominant, round(confidence, 2))


def check_language_consistency(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Check if all text fields in a sample have consistent language.

    Returns False if fields have different dominant languages.
    """
    data = sample.get("data", sample)
    languages = []

    for value in data.values():
        if isinstance(value, str) and len(value) > 10:
            lang, confidence = detect_language(value)
            if lang != "unknown" and confidence > 0.3:
                languages.append(lang)

    if len(languages) < 2:
        return True

    return len(set(languages)) == 1


# --- PII detection ---

PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_cn": re.compile(r"1[3-9]\d{9}"),
    "phone_intl": re.compile(r"\+\d{1,3}[-.\s]?\d{4,14}"),
    "id_cn": re.compile(r"\d{17}[\dXx]"),
}


def check_pii(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Check for PII (email, phone, ID numbers). Returns False if PII found."""
    data = sample.get("data", sample)
    for value in data.values():
        if not isinstance(value, str):
            continue
        for pattern in PII_PATTERNS.values():
            if pattern.search(value):
                return False
    return True


# --- Garbled text detection ---

GARBLED_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd\ufffe\uffff]")
ENCODING_ERROR_PATTERN = re.compile(r"[\u00c0-\u00ff]{3,}")


def check_garbled_text(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Check for garbled or abnormal characters. Returns False if garbled."""
    data = sample.get("data", sample)
    for value in data.values():
        if not isinstance(value, str) or len(value) < 5:
            continue
        garbled_count = len(GARBLED_PATTERN.findall(value))
        if garbled_count > 0 and garbled_count / len(value) > 0.01:
            return False
        if ENCODING_ERROR_PATTERN.search(value):
            return False
    return True


# --- Repetitive text detection ---


def check_repetitive_text(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Check if text contains excessive repetition. Returns False if repetitive."""
    data = sample.get("data", sample)
    for value in data.values():
        if not isinstance(value, str) or len(value) < 50:
            continue

        # Split into sentences
        segments = re.split(r"[。！？\n.!?]+", value)
        segments = [s.strip() for s in segments if len(s.strip()) > 5]

        if len(segments) >= 3:
            counter = Counter(segments)
            most_common_count = counter.most_common(1)[0][1]
            if most_common_count >= 3 and most_common_count / len(segments) > 0.3:
                return False

        # Character-level repetition (e.g., same 10-char block repeated)
        if len(value) > 100:
            window_size = 10
            windows = [
                value[i : i + window_size]
                for i in range(0, len(value) - window_size, window_size)
            ]
            if windows:
                window_counter = Counter(windows)
                top_count = window_counter.most_common(1)[0][1]
                if top_count / len(windows) > 0.5 and top_count > 3:
                    return False

    return True
