"""Core data quality checker."""

import csv
import json
import hashlib
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from datacheck.rules import RuleSet, Severity


@dataclass
class CheckResult:
    """Result of quality check."""

    success: bool = True
    error: str = ""
    total_samples: int = 0
    passed_samples: int = 0
    failed_samples: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    pass_rate: float = 0.0
    rule_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_sample_ids: List[str] = field(default_factory=list)
    duplicates: List[List[str]] = field(default_factory=list)
    distribution: Dict[str, Any] = field(default_factory=dict)
    near_duplicates: List[List[str]] = field(default_factory=list)
    anomalies: Dict[str, Any] = field(default_factory=dict)
    anomaly_count: int = 0
    sampled: bool = False
    sampled_count: int = 0
    original_count: int = 0


SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".csv"}


@dataclass
class BatchCheckResult:
    """Result of batch directory check."""

    success: bool = True
    error: str = ""
    directory: str = ""
    file_results: Dict[str, CheckResult] = field(default_factory=dict)
    total_files: int = 0
    passed_files: int = 0
    failed_files: int = 0
    total_samples: int = 0
    total_passed_samples: int = 0
    total_failed_samples: int = 0
    overall_pass_rate: float = 0.0
    total_error_count: int = 0
    total_warning_count: int = 0
    total_info_count: int = 0
    skipped_files: List[str] = field(default_factory=list)


class DataChecker:
    """Check data quality against rules and schema.

    Provides:
    - Rule-based validation
    - Duplicate detection
    - Distribution analysis
    - Anomaly detection
    """

    def __init__(self, ruleset: Optional[RuleSet] = None):
        self.ruleset = ruleset or RuleSet()

    def check(
        self,
        samples: List[Dict[str, Any]],
        schema: Dict[str, Any],
        reference_samples: Optional[List[Dict[str, Any]]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> CheckResult:
        """Check samples against schema and rules.

        Args:
            samples: List of samples to check
            schema: Data schema definition
            reference_samples: Optional reference samples for comparison
            on_progress: Progress callback

        Returns:
            CheckResult with check status and details
        """
        result = CheckResult()
        result.total_samples = len(samples)

        if not samples:
            result.success = True
            result.pass_rate = 1.0
            return result

        # Per-rule statistics
        rule_stats = defaultdict(lambda: {"passed": 0, "failed": 0, "sample_ids": []})

        # Check each sample
        sample_failures = defaultdict(list)
        passed_count = 0

        for i, sample in enumerate(samples):
            sample_id = sample.get("id", f"sample_{i}")
            sample_has_error = False  # Only ERROR severity counts as failure

            for rule in self.ruleset.get_enabled_rules():
                rule_result = rule.check(sample, schema)

                if rule_result.passed:
                    rule_stats[rule.id]["passed"] += 1
                else:
                    rule_stats[rule.id]["failed"] += 1
                    rule_stats[rule.id]["sample_ids"].append(sample_id)
                    sample_failures[sample_id].append(rule_result)

                    # Count by severity - only ERROR marks sample as failed
                    if rule_result.severity == Severity.ERROR:
                        result.error_count += 1
                        sample_has_error = True
                    elif rule_result.severity == Severity.WARNING:
                        result.warning_count += 1
                    else:
                        result.info_count += 1

            if not sample_has_error:
                passed_count += 1
            else:
                result.failed_sample_ids.append(sample_id)

            if on_progress:
                on_progress(i + 1, len(samples))

        result.passed_samples = passed_count
        result.failed_samples = len(samples) - passed_count
        result.pass_rate = passed_count / len(samples) if samples else 1.0

        # Build rule results summary
        for rule_id, stats in rule_stats.items():
            rule = self.ruleset.rules.get(rule_id)
            result.rule_results[rule_id] = {
                "name": rule.name if rule else rule_id,
                "passed": stats["passed"],
                "failed": stats["failed"],
                "severity": rule.severity.value if rule else "warning",
                "failed_samples": stats["sample_ids"][:10],  # Limit to 10
            }

        # Check for duplicates
        result.duplicates = self._find_duplicates(samples)
        if result.duplicates:
            result.warning_count += len(result.duplicates)

        # Check for near-duplicates
        result.near_duplicates = self._find_near_duplicates(samples)
        if result.near_duplicates:
            result.warning_count += len(result.near_duplicates)

        # Compute distribution
        result.distribution = self._compute_distribution(samples, schema)

        # Anomaly detection
        from datacheck.anomaly import detect_anomalies
        result.anomalies = detect_anomalies(samples)
        result.anomaly_count = sum(a["outlier_count"] for a in result.anomalies.values())

        # Compare with reference if provided
        if reference_samples:
            result.distribution["reference_comparison"] = self._compare_distributions(
                samples, reference_samples, schema
            )

        return result

    @staticmethod
    def _load_data(data_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Load data from file, detecting format by extension.

        Supports .json, .jsonl, .csv formats.

        Returns:
            (samples, schema) tuple
        """
        suffix = data_path.suffix.lower()

        if suffix == ".jsonl":
            samples = []
            with open(data_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        samples.append(json.loads(line))
            return samples, {}

        elif suffix == ".csv":
            with open(data_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                samples = list(reader)
            return samples, {}

        else:  # .json default
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                return data, {}

            samples = data.get("samples", data.get("responses", []))
            schema = data.get("schema", {})
            return samples, schema

    def check_file(
        self,
        data_path: str,
        schema_path: Optional[str] = None,
        output_path: Optional[str] = None,
        sample_count: Optional[int] = None,
        sample_rate: Optional[float] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> CheckResult:
        """Check a data file.

        Args:
            data_path: Path to data file (JSON/JSONL/CSV)
            schema_path: Path to schema JSON file (optional)
            output_path: Path to save report (optional)
            sample_count: Random sample N items (optional)
            sample_rate: Random sample ratio 0-1 (optional)

        Returns:
            CheckResult
        """
        data_path = Path(data_path)

        # Load data
        samples, embedded_schema = self._load_data(data_path)

        # Load schema
        schema = {}
        if schema_path:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        elif embedded_schema:
            schema = embedded_schema

        # Sampling
        original_count = len(samples)
        sampled = False

        if sample_count is not None and sample_count < len(samples):
            samples = random.sample(samples, sample_count)
            sampled = True
        elif sample_rate is not None and 0 < sample_rate < 1.0:
            k = max(1, int(len(samples) * sample_rate))
            samples = random.sample(samples, k)
            sampled = True

        # Run check
        result = self.check(samples, schema, on_progress=on_progress)

        if sampled:
            result.sampled = True
            result.sampled_count = len(samples)
            result.original_count = original_count

        # Save report if output path provided
        if output_path:
            self._save_report(result, output_path)

        return result

    def check_directory(
        self,
        dir_path: str,
        schema_path: Optional[str] = None,
        patterns: Optional[List[str]] = None,
        sample_count: Optional[int] = None,
        sample_rate: Optional[float] = None,
        on_file_start: Optional[Callable[[str, int, int], None]] = None,
    ) -> BatchCheckResult:
        """Check all data files in a directory.

        Args:
            dir_path: Path to directory
            schema_path: Path to schema JSON file (optional)
            patterns: File glob patterns (default: *.json, *.jsonl, *.csv)
            sample_count: Random sample N items per file (optional)
            sample_rate: Random sample ratio per file (optional)
            on_file_start: Callback(relative_path, current_index, total_count)

        Returns:
            BatchCheckResult with per-file results and aggregate stats
        """
        dir_path = Path(dir_path)
        result = BatchCheckResult(directory=str(dir_path))

        if not dir_path.is_dir():
            result.success = False
            result.error = f"不是目录: {dir_path}"
            return result

        # Collect files
        if patterns is None:
            patterns = [f"*{ext}" for ext in SUPPORTED_EXTENSIONS]

        files: set = set()
        for pat in patterns:
            files.update(dir_path.rglob(pat))

        # Filter to supported extensions and sort
        file_list = sorted(
            f for f in files
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        result.total_files = len(file_list)

        if not file_list:
            result.overall_pass_rate = 1.0
            return result

        # Check each file
        for idx, file_path in enumerate(file_list):
            rel_path = str(file_path.relative_to(dir_path))

            if on_file_start:
                on_file_start(rel_path, idx + 1, len(file_list))

            try:
                file_result = self.check_file(
                    str(file_path),
                    schema_path=schema_path,
                    sample_count=sample_count,
                    sample_rate=sample_rate,
                )
                result.file_results[rel_path] = file_result
                result.total_samples += file_result.total_samples
                result.total_passed_samples += file_result.passed_samples
                result.total_failed_samples += file_result.failed_samples
                result.total_error_count += file_result.error_count
                result.total_warning_count += file_result.warning_count
                result.total_info_count += file_result.info_count
            except Exception as e:
                result.skipped_files.append(f"{rel_path}: {e}")

        # Aggregate
        if result.total_samples > 0:
            result.overall_pass_rate = result.total_passed_samples / result.total_samples
        else:
            result.overall_pass_rate = 1.0

        result.passed_files = sum(
            1 for r in result.file_results.values() if r.error_count == 0
        )
        result.failed_files = result.total_files - result.passed_files - len(result.skipped_files)

        return result

    def check_from_datarecipe(
        self,
        analysis_dir: str,
        data_path: Optional[str] = None,
    ) -> CheckResult:
        """Check data using DataRecipe analysis output.

        Args:
            analysis_dir: Path to DataRecipe analysis output
            data_path: Path to data file to check (optional, defaults to synthetic data)

        Returns:
            CheckResult
        """
        analysis_dir = Path(analysis_dir)

        # Load schema
        schema_path = analysis_dir / "04_复刻指南" / "DATA_SCHEMA.json"
        if not schema_path.exists():
            return CheckResult(success=False, error=f"Schema not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Determine data path
        if data_path is None:
            # Try synthetic data first, then samples
            synthetic_path = analysis_dir / "11_合成数据" / "synthetic.json"
            samples_path = analysis_dir / "09_样例数据" / "samples.json"

            if synthetic_path.exists():
                data_path = synthetic_path
            elif samples_path.exists():
                data_path = samples_path
            else:
                return CheckResult(success=False, error="No data file found")
        else:
            data_path = Path(data_path)

        # Load data
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        samples = data.get("samples", [])

        # Load reference samples for comparison
        reference = None
        ref_path = analysis_dir / "09_样例数据" / "samples.json"
        if ref_path.exists() and str(ref_path) != str(data_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                ref_data = json.load(f)
                reference = ref_data.get("samples", [])

        return self.check(samples, schema, reference_samples=reference)

    def _find_duplicates(self, samples: List[Dict[str, Any]]) -> List[List[str]]:
        """Find duplicate samples."""
        # Hash each sample's content
        hash_to_ids = defaultdict(list)

        for i, sample in enumerate(samples):
            sample_id = sample.get("id", f"sample_{i}")
            data = sample.get("data", sample)

            # Create content hash
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
            content_hash = hashlib.md5(content.encode()).hexdigest()

            hash_to_ids[content_hash].append(sample_id)

        # Find duplicates
        duplicates = [ids for ids in hash_to_ids.values() if len(ids) > 1]
        return duplicates

    def _find_near_duplicates(
        self, samples: List[Dict[str, Any]], threshold: float = 0.8
    ) -> List[List[str]]:
        """Find near-duplicate samples using n-gram Jaccard similarity."""
        from datacheck.text_rules import compute_ngrams, jaccard_similarity

        if len(samples) > 5000:
            return []

        sample_ngrams = []
        for i, sample in enumerate(samples):
            sample_id = sample.get("id", f"sample_{i}")
            data = sample.get("data", sample)
            text = " ".join(str(v) for v in data.values() if isinstance(v, str))
            ngrams = compute_ngrams(text, n=3)
            sample_ngrams.append((sample_id, ngrams))

        near_dupes = []
        seen: set = set()

        for i in range(len(sample_ngrams)):
            if sample_ngrams[i][0] in seen:
                continue
            group = [sample_ngrams[i][0]]
            for j in range(i + 1, len(sample_ngrams)):
                if sample_ngrams[j][0] in seen:
                    continue
                sim = jaccard_similarity(sample_ngrams[i][1], sample_ngrams[j][1])
                if sim >= threshold:
                    group.append(sample_ngrams[j][0])
                    seen.add(sample_ngrams[j][0])
            if len(group) > 1:
                near_dupes.append(group)
                seen.add(sample_ngrams[i][0])

        return near_dupes

    def _compute_distribution(
        self,
        samples: List[Dict[str, Any]],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute distribution statistics."""
        distribution = {
            "total": len(samples),
            "fields": {},
        }

        if not samples:
            return distribution

        # Analyze each field
        field_values = defaultdict(list)

        for sample in samples:
            data = sample.get("data", sample)
            for key, value in data.items():
                field_values[key].append(value)

        for field_name, values in field_values.items():
            field_stats = {
                "count": len(values),
                "null_count": sum(1 for v in values if v is None),
            }

            # String stats
            string_values = [v for v in values if isinstance(v, str)]
            if string_values:
                lengths = [len(v) for v in string_values]
                field_stats["type"] = "string"
                field_stats["length_stats"] = {
                    "min": min(lengths),
                    "max": max(lengths),
                    "avg": sum(lengths) / len(lengths),
                }

                # Unique ratio
                unique_count = len(set(string_values))
                field_stats["unique_count"] = unique_count
                field_stats["unique_ratio"] = unique_count / len(string_values)

            # Number stats
            number_values = [v for v in values if isinstance(v, (int, float))]
            if number_values:
                field_stats["type"] = "number"
                field_stats["value_stats"] = {
                    "min": min(number_values),
                    "max": max(number_values),
                    "avg": sum(number_values) / len(number_values),
                }

                # Value distribution
                counter = Counter(number_values)
                field_stats["value_distribution"] = dict(counter.most_common(10))

            distribution["fields"][field_name] = field_stats

        return distribution

    def _compare_distributions(
        self,
        samples: List[Dict[str, Any]],
        reference: List[Dict[str, Any]],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare distribution with reference samples."""
        comparison = {
            "sample_count": len(samples),
            "reference_count": len(reference),
            "field_comparisons": {},
        }

        # Get distributions
        sample_dist = self._compute_distribution(samples, schema)
        ref_dist = self._compute_distribution(reference, schema)

        # Compare each field
        for field_name in set(sample_dist["fields"].keys()) | set(ref_dist["fields"].keys()):
            sample_field = sample_dist["fields"].get(field_name, {})
            ref_field = ref_dist["fields"].get(field_name, {})

            field_comparison = {
                "in_samples": field_name in sample_dist["fields"],
                "in_reference": field_name in ref_dist["fields"],
            }

            # Compare lengths for strings
            if "length_stats" in sample_field and "length_stats" in ref_field:
                s_len = sample_field["length_stats"]
                r_len = ref_field["length_stats"]
                field_comparison["length_comparison"] = {
                    "sample_avg": s_len["avg"],
                    "reference_avg": r_len["avg"],
                    "diff_percent": abs(s_len["avg"] - r_len["avg"]) / r_len["avg"] * 100
                    if r_len["avg"] > 0
                    else 0,
                }

            # Compare unique ratios
            if "unique_ratio" in sample_field and "unique_ratio" in ref_field:
                field_comparison["diversity_comparison"] = {
                    "sample_unique_ratio": sample_field["unique_ratio"],
                    "reference_unique_ratio": ref_field["unique_ratio"],
                }

            comparison["field_comparisons"][field_name] = field_comparison

        return comparison

    @staticmethod
    def infer_schema(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Infer schema from sample data.

        Detects field names, types, constraints, and generates a schema
        compatible with DataCheck's validation format.

        Args:
            samples: List of sample dicts

        Returns:
            Inferred schema dict
        """
        if not samples:
            return {"fields": {}, "sample_count": 0}

        field_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "types": Counter(), "lengths": [], "values": []}
        )

        for sample in samples:
            data = sample.get("data", sample)
            for key, value in data.items():
                fs = field_stats[key]
                fs["count"] += 1

                if value is None:
                    fs["types"]["null"] += 1
                elif isinstance(value, str):
                    fs["types"]["string"] += 1
                    fs["lengths"].append(len(value))
                elif isinstance(value, bool):
                    fs["types"]["boolean"] += 1
                elif isinstance(value, int):
                    fs["types"]["integer"] += 1
                    fs["values"].append(value)
                elif isinstance(value, float):
                    fs["types"]["number"] += 1
                    fs["values"].append(value)
                elif isinstance(value, list):
                    fs["types"]["array"] += 1
                elif isinstance(value, dict):
                    fs["types"]["object"] += 1

        total = len(samples)
        fields = {}

        for fname, fs in field_stats.items():
            # Determine primary type (most common non-null type)
            type_counts = {k: v for k, v in fs["types"].items() if k != "null"}
            primary_type = max(type_counts, key=type_counts.get) if type_counts else "string"

            field_def: Dict[str, Any] = {"type": primary_type}

            # Required if present in >= 95% of samples
            presence_rate = fs["count"] / total
            if presence_rate >= 0.95:
                field_def["required"] = True

            # Null rate
            null_count = fs["types"].get("null", 0)
            if null_count > 0:
                field_def["nullable"] = True

            # String constraints
            if primary_type == "string" and fs["lengths"]:
                field_def["min_length"] = min(fs["lengths"])
                field_def["max_length"] = max(fs["lengths"])
                field_def["avg_length"] = round(sum(fs["lengths"]) / len(fs["lengths"]))

            # Number constraints
            if primary_type in ("integer", "number") and fs["values"]:
                field_def["min_value"] = min(fs["values"])
                field_def["max_value"] = max(fs["values"])
                # If values are within a small set, suggest enum
                unique_vals = set(fs["values"])
                if len(unique_vals) <= 10:
                    field_def["enum"] = sorted(unique_vals)

            fields[fname] = field_def

        return {
            "sample_count": total,
            "fields": fields,
        }

    def infer_schema_file(self, data_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Infer schema from a data file.

        Args:
            data_path: Path to data file (JSON/JSONL/CSV)
            output_path: Optional path to save schema

        Returns:
            Inferred schema dict
        """
        samples, _ = self._load_data(Path(data_path))
        schema = self.infer_schema(samples)

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

        return schema

    def _save_report(self, result: CheckResult, output_path: str):
        """Save check report to file."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_samples": result.total_samples,
                "passed_samples": result.passed_samples,
                "failed_samples": result.failed_samples,
                "pass_rate": f"{result.pass_rate:.1%}",
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "info_count": result.info_count,
            },
            "rule_results": result.rule_results,
            "duplicates": result.duplicates,
            "distribution": result.distribution,
            "failed_sample_ids": result.failed_sample_ids[:50],  # Limit
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
