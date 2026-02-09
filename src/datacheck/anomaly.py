"""统计异常检测模块。

基于 IQR 和 Z-score 方法检测数值和字符串长度异常值。
纯 Python 实现，无 numpy/scipy 依赖。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List


MIN_SAMPLES = 10  # 最少样本数才做检测


def compute_stats(values: list[float]) -> dict[str, float]:
    """计算基础统计量。

    返回: {mean, std, median, q1, q3, iqr}
    """
    if not values:
        return {"mean": 0, "std": 0, "median": 0, "q1": 0, "q3": 0, "iqr": 0}

    n = len(values)
    sorted_vals = sorted(values)

    mean = sum(sorted_vals) / n

    if n == 1:
        return {"mean": mean, "std": 0, "median": mean, "q1": mean, "q3": mean, "iqr": 0}

    # 标准差
    variance = sum((x - mean) ** 2 for x in sorted_vals) / n
    std = math.sqrt(variance)

    # 中位数
    median = _percentile(sorted_vals, 0.5)
    q1 = _percentile(sorted_vals, 0.25)
    q3 = _percentile(sorted_vals, 0.75)
    iqr = q3 - q1

    return {"mean": mean, "std": std, "median": median, "q1": q1, "q3": q3, "iqr": iqr}


def _percentile(sorted_vals: list[float], p: float) -> float:
    """计算百分位数 (线性插值)。"""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def detect_outliers_zscore(values: list[float], threshold: float = 3.0) -> list[int]:
    """Z-score 异常检测，返回异常值的索引列表。"""
    if len(values) < MIN_SAMPLES:
        return []

    stats = compute_stats(values)
    if stats["std"] == 0:
        return []

    outliers = []
    for i, v in enumerate(values):
        z = abs(v - stats["mean"]) / stats["std"]
        if z > threshold:
            outliers.append(i)
    return outliers


def detect_outliers_iqr(values: list[float], factor: float = 1.5) -> list[int]:
    """IQR 异常检测，返回异常值的索引列表。"""
    if len(values) < MIN_SAMPLES:
        return []

    stats = compute_stats(values)
    iqr = stats["iqr"]

    if iqr == 0:
        return []

    lower = stats["q1"] - factor * iqr
    upper = stats["q3"] + factor * iqr

    outliers = []
    for i, v in enumerate(values):
        if v < lower or v > upper:
            outliers.append(i)
    return outliers


def detect_anomalies(
    samples: List[Dict[str, Any]],
    method: str = "iqr",
    factor: float = 1.5,
    zscore_threshold: float = 3.0,
) -> Dict[str, Any]:
    """检测所有字段的异常值。

    对数值字段直接检测，对字符串字段检测长度异常。

    Args:
        samples: 样本列表
        method: 检测方法 ("iqr" 或 "zscore")
        factor: IQR 倍数 (默认 1.5)
        zscore_threshold: Z-score 阈值 (默认 3.0)

    Returns:
        {field_name: {stats, outlier_indices, outlier_count, method, bounds}}
    """
    if len(samples) < MIN_SAMPLES:
        return {}

    # 收集每个字段的值
    field_values: Dict[str, List[float]] = {}
    field_types: Dict[str, str] = {}  # "number" 或 "length"

    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for key, val in sample.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                field_values.setdefault(key, []).append(float(val))
                field_types[key] = "number"
            elif isinstance(val, str):
                length_key = f"{key} (长度)"
                field_values.setdefault(length_key, []).append(float(len(val)))
                field_types[length_key] = "length"

    results: Dict[str, Any] = {}

    for field_name, values in field_values.items():
        if len(values) < MIN_SAMPLES:
            continue

        stats = compute_stats(values)

        if method == "zscore":
            outlier_indices = detect_outliers_zscore(values, zscore_threshold)
        else:
            outlier_indices = detect_outliers_iqr(values, factor)

        if not outlier_indices:
            continue

        # 计算正常范围边界
        iqr = stats["iqr"]
        lower = stats["q1"] - factor * iqr
        upper = stats["q3"] + factor * iqr

        results[field_name] = {
            "stats": stats,
            "outlier_indices": outlier_indices,
            "outlier_count": len(outlier_indices),
            "method": method,
            "field_type": field_types[field_name],
            "bounds": {"lower": round(lower, 2), "upper": round(upper, 2)},
        }

    return results
