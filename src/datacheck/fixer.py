"""Data fixer - automated data cleaning and repair."""

import json
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class FixResult:
    """Result of data fixing."""

    total_input: int = 0
    total_output: int = 0
    duplicates_removed: int = 0
    empty_removed: int = 0
    trimmed_count: int = 0
    pii_redacted_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


# PII patterns for redaction
_PII_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # ID card must come before phone to avoid partial match
    (re.compile(r"\d{6}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]"), "[ID]"),
    (re.compile(r"1[3-9]\d{9}"), "[PHONE]"),
    (re.compile(r"\+\d{1,3}[-.\s]?\d{4,14}"), "[PHONE]"),
]


class DataFixer:
    """Fix common data quality issues."""

    def fix(
        self,
        samples: List[Dict[str, Any]],
        dedup: bool = True,
        trim: bool = True,
        remove_empty: bool = True,
        strip_pii: bool = False,
    ) -> tuple:
        """Fix samples and return (fixed_samples, fix_result).

        Args:
            samples: Input samples
            dedup: Remove exact duplicates
            trim: Strip whitespace from string fields
            remove_empty: Remove samples with all empty/null fields
            strip_pii: Redact PII patterns

        Returns:
            (fixed_samples, FixResult) tuple
        """
        result = FixResult(total_input=len(samples))
        fixed = list(samples)

        # 1. Deduplication
        if dedup:
            fixed, removed = self._dedup(fixed)
            result.duplicates_removed = removed

        # 2. Trim whitespace
        if trim:
            fixed, trimmed = self._trim(fixed)
            result.trimmed_count = trimmed

        # 3. Remove empty samples
        if remove_empty:
            fixed, removed = self._remove_empty(fixed)
            result.empty_removed = removed

        # 4. Strip PII
        if strip_pii:
            fixed, redacted = self._strip_pii(fixed)
            result.pii_redacted_count = redacted

        result.total_output = len(fixed)
        return fixed, result

    def fix_file(
        self,
        data_path: str,
        output_path: str,
        dedup: bool = True,
        trim: bool = True,
        remove_empty: bool = True,
        strip_pii: bool = False,
    ) -> FixResult:
        """Fix a data file and save results.

        Args:
            data_path: Input file path (JSON/JSONL/CSV)
            output_path: Output file path (JSONL)
            dedup: Remove exact duplicates
            trim: Strip whitespace
            remove_empty: Remove empty samples
            strip_pii: Redact PII

        Returns:
            FixResult
        """
        from datacheck.checker import DataChecker

        samples, _ = DataChecker._load_data(Path(data_path))
        fixed, result = self.fix(
            samples, dedup=dedup, trim=trim, remove_empty=remove_empty, strip_pii=strip_pii
        )

        # Save as JSONL
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for sample in fixed:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        return result

    @staticmethod
    def _dedup(samples: List[Dict[str, Any]]) -> tuple:
        """Remove exact duplicate samples. Returns (deduped, removed_count)."""
        seen = set()
        deduped = []
        removed = 0

        for sample in samples:
            data = sample.get("data", sample)
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
            h = hashlib.md5(content.encode()).hexdigest()

            if h not in seen:
                seen.add(h)
                deduped.append(sample)
            else:
                removed += 1

        return deduped, removed

    @staticmethod
    def _trim(samples: List[Dict[str, Any]]) -> tuple:
        """Trim whitespace from string fields. Returns (trimmed_samples, count)."""
        count = 0

        for sample in samples:
            data = sample.get("data", sample)
            for key, value in data.items():
                if isinstance(value, str):
                    trimmed = value.strip()
                    if trimmed != value:
                        data[key] = trimmed
                        count += 1

        return samples, count

    @staticmethod
    def _remove_empty(samples: List[Dict[str, Any]]) -> tuple:
        """Remove samples where all fields are empty/null. Returns (cleaned, removed_count)."""
        cleaned = []
        removed = 0

        for sample in samples:
            data = sample.get("data", sample)
            has_value = any(
                v is not None and v != "" and v != [] and v != {}
                for v in data.values()
            )
            if has_value:
                cleaned.append(sample)
            else:
                removed += 1

        return cleaned, removed

    @staticmethod
    def _strip_pii(samples: List[Dict[str, Any]]) -> tuple:
        """Replace PII patterns with redaction tokens. Returns (cleaned, redacted_count)."""
        count = 0

        for sample in samples:
            data = sample.get("data", sample)
            for key, value in data.items():
                if isinstance(value, str):
                    new_value = value
                    for pattern, replacement in _PII_PATTERNS:
                        new_value = pattern.sub(replacement, new_value)
                    if new_value != value:
                        data[key] = new_value
                        count += 1

        return samples, count
