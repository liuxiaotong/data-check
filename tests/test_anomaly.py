"""Tests for anomaly detection module."""

import pytest

from datacheck.anomaly import (
    compute_stats,
    detect_anomalies,
    detect_outliers_iqr,
    detect_outliers_zscore,
)


class TestComputeStats:
    """Tests for compute_stats()."""

    def test_basic_stats(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        stats = compute_stats(values)
        assert stats["mean"] == pytest.approx(5.5)
        assert stats["q1"] == pytest.approx(3.25)
        assert stats["q3"] == pytest.approx(7.75)
        assert stats["iqr"] == pytest.approx(4.5)
        assert stats["std"] > 0

    def test_empty_values(self):
        stats = compute_stats([])
        assert stats["mean"] == 0
        assert stats["std"] == 0
        assert stats["iqr"] == 0

    def test_single_value(self):
        stats = compute_stats([42.0])
        assert stats["mean"] == 42.0
        assert stats["std"] == 0
        assert stats["q1"] == 42.0
        assert stats["q3"] == 42.0
        assert stats["iqr"] == 0

    def test_two_values(self):
        stats = compute_stats([1.0, 3.0])
        assert stats["mean"] == pytest.approx(2.0)
        assert stats["median"] == pytest.approx(2.0)


class TestOutlierDetection:
    """Tests for outlier detection functions."""

    def test_zscore_outliers(self):
        # Normal values with one extreme outlier
        values = [10, 10, 11, 10, 9, 10, 11, 10, 9, 10, 100]
        outliers = detect_outliers_zscore(values, threshold=2.0)
        assert len(outliers) >= 1
        assert 10 in outliers  # index of 100

    def test_zscore_too_few(self):
        values = [1, 2, 3]
        assert detect_outliers_zscore(values) == []

    def test_zscore_no_variation(self):
        values = [5] * 20
        assert detect_outliers_zscore(values) == []

    def test_iqr_outliers(self):
        # Normal values with outliers
        values = [10, 11, 10, 9, 10, 11, 10, 9, 10, 10, 50]
        outliers = detect_outliers_iqr(values)
        assert len(outliers) >= 1
        assert 10 in outliers  # index of 50

    def test_iqr_no_outliers(self):
        values = list(range(1, 21))  # 1 to 20, evenly spread
        outliers = detect_outliers_iqr(values)
        assert outliers == []

    def test_iqr_too_few(self):
        values = [1, 2, 3]
        assert detect_outliers_iqr(values) == []

    def test_iqr_no_variation(self):
        values = [5] * 20
        assert detect_outliers_iqr(values) == []


class TestDetectAnomalies:
    """Tests for detect_anomalies()."""

    def test_number_field(self):
        samples = [{"score": float(i)} for i in range(20)]
        samples.append({"score": 1000.0})  # outlier

        result = detect_anomalies(samples)
        assert "score" in result
        assert result["score"]["outlier_count"] >= 1
        assert result["score"]["field_type"] == "number"
        assert result["score"]["method"] == "iqr"
        assert "bounds" in result["score"]

    def test_string_length(self):
        # Vary string lengths slightly so IQR is non-zero
        samples = [{"text": "a" * (5 + i % 3)} for i in range(20)]
        samples.append({"text": "x" * 1000})  # very long string outlier

        result = detect_anomalies(samples)
        assert "text (长度)" in result
        assert result["text (长度)"]["outlier_count"] >= 1
        assert result["text (长度)"]["field_type"] == "length"

    def test_mixed_fields(self):
        samples = []
        for i in range(20):
            samples.append({"text": f"word{i}", "score": float(i)})
        samples.append({"text": "x" * 500, "score": 999.0})

        result = detect_anomalies(samples)
        # Should detect anomalies in both fields
        assert len(result) >= 1

    def test_too_few_samples(self):
        samples = [{"score": 1.0}, {"score": 2.0}]
        result = detect_anomalies(samples)
        assert result == {}

    def test_no_anomalies(self):
        # All values are very close
        samples = [{"score": 10.0 + i * 0.01} for i in range(20)]
        result = detect_anomalies(samples)
        assert "score" not in result

    def test_zscore_method(self):
        samples = [{"val": float(i)} for i in range(20)]
        samples.append({"val": 1000.0})

        result = detect_anomalies(samples, method="zscore")
        assert "val" in result
        assert result["val"]["method"] == "zscore"

    def test_non_dict_samples_skipped(self):
        samples = [{"score": 1.0}] * 15 + ["not a dict"] * 5 + [{"score": 999.0}]
        result = detect_anomalies(samples)
        # Should not crash, just skip non-dict items
        assert isinstance(result, dict)

    def test_boolean_not_treated_as_number(self):
        samples = [{"flag": True, "score": float(i)} for i in range(20)]
        samples.append({"flag": False, "score": 999.0})
        result = detect_anomalies(samples)
        # "flag" should not appear as a number field
        assert "flag" not in result
