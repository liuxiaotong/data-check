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
