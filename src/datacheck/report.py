"""Quality report generation."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from datacheck.checker import CheckResult
from datacheck.rules import Severity


@dataclass
class QualityReport:
    """Generate human-readable quality reports."""

    result: CheckResult
    title: str = "数据质量报告"

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# {self.title}",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 概要",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总样本数 | {self.result.total_samples} |",
            f"| 通过样本 | {self.result.passed_samples} |",
            f"| 失败样本 | {self.result.failed_samples} |",
            f"| **通过率** | **{self.result.pass_rate:.1%}** |",
            "",
        ]

        # Quality score visualization
        score = self.result.pass_rate * 100
        if score >= 90:
            grade = "🟢 优秀"
        elif score >= 70:
            grade = "🟡 良好"
        elif score >= 50:
            grade = "🟠 一般"
        else:
            grade = "🔴 需改进"

        lines.extend([
            f"### 质量评级: {grade} ({score:.0f}分)",
            "",
        ])

        # Issue summary
        if self.result.error_count or self.result.warning_count:
            lines.extend([
                "### 问题统计",
                "",
                f"| 级别 | 数量 |",
                f"|------|------|",
                f"| 🔴 错误 | {self.result.error_count} |",
                f"| 🟡 警告 | {self.result.warning_count} |",
                f"| 🔵 提示 | {self.result.info_count} |",
                "",
            ])

        # Rule results
        if self.result.rule_results:
            lines.extend([
                "---",
                "",
                "## 规则检查详情",
                "",
            ])

            for rule_id, rule_data in self.result.rule_results.items():
                severity = rule_data.get("severity", "warning")
                icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
                status = "✅" if rule_data["failed"] == 0 else "❌"

                lines.append(f"### {icon} {rule_data['name']} {status}")
                lines.append("")
                lines.append(f"- 通过: {rule_data['passed']}")
                lines.append(f"- 失败: {rule_data['failed']}")

                if rule_data["failed_samples"]:
                    lines.append(f"- 失败样本: {', '.join(rule_data['failed_samples'][:5])}")
                    if len(rule_data["failed_samples"]) > 5:
                        lines.append(f"  (还有 {len(rule_data['failed_samples']) - 5} 个...)")

                lines.append("")

        # Duplicates
        if self.result.duplicates:
            lines.extend([
                "---",
                "",
                "## 重复检测",
                "",
                f"发现 **{len(self.result.duplicates)}** 组重复数据:",
                "",
            ])

            for i, dup_group in enumerate(self.result.duplicates[:10], 1):
                lines.append(f"{i}. {', '.join(dup_group)}")

            if len(self.result.duplicates) > 10:
                lines.append(f"\n(还有 {len(self.result.duplicates) - 10} 组...)")

            lines.append("")

        # Distribution
        if self.result.distribution.get("fields"):
            lines.extend([
                "---",
                "",
                "## 数据分布",
                "",
            ])

            for field_name, field_stats in self.result.distribution["fields"].items():
                lines.append(f"### {field_name}")
                lines.append("")

                if "length_stats" in field_stats:
                    stats = field_stats["length_stats"]
                    lines.append(f"- 长度: 最小 {stats['min']}, 最大 {stats['max']}, 平均 {stats['avg']:.0f}")

                if "unique_ratio" in field_stats:
                    lines.append(f"- 唯一值比例: {field_stats['unique_ratio']:.1%}")

                if "value_distribution" in field_stats:
                    lines.append("- 值分布:")
                    for val, count in list(field_stats["value_distribution"].items())[:5]:
                        lines.append(f"  - {val}: {count}")

                lines.append("")

        # Reference comparison
        if "reference_comparison" in self.result.distribution:
            comp = self.result.distribution["reference_comparison"]
            lines.extend([
                "---",
                "",
                "## 与参考数据对比",
                "",
                f"样本数量: {comp['sample_count']} vs 参考: {comp['reference_count']}",
                "",
            ])

            for field_name, field_comp in comp.get("field_comparisons", {}).items():
                if "length_comparison" in field_comp:
                    lc = field_comp["length_comparison"]
                    lines.append(f"- **{field_name}** 平均长度: {lc['sample_avg']:.0f} vs {lc['reference_avg']:.0f} ({lc['diff_percent']:.1f}% 差异)")

            lines.append("")

        # Failed samples
        if self.result.failed_sample_ids:
            lines.extend([
                "---",
                "",
                "## 失败样本列表",
                "",
                f"共 {len(self.result.failed_sample_ids)} 个样本未通过检查:",
                "",
            ])

            for sid in self.result.failed_sample_ids[:20]:
                lines.append(f"- {sid}")

            if len(self.result.failed_sample_ids) > 20:
                lines.append(f"\n(还有 {len(self.result.failed_sample_ids) - 20} 个...)")

        lines.extend([
            "",
            "---",
            "",
            "> 报告由 DataCheck 自动生成",
        ])

        return "\n".join(lines)

    def to_json(self) -> Dict[str, Any]:
        """Generate JSON report."""
        return {
            "title": self.title,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_samples": self.result.total_samples,
                "passed_samples": self.result.passed_samples,
                "failed_samples": self.result.failed_samples,
                "pass_rate": self.result.pass_rate,
                "error_count": self.result.error_count,
                "warning_count": self.result.warning_count,
                "info_count": self.result.info_count,
            },
            "rule_results": self.result.rule_results,
            "duplicates": self.result.duplicates,
            "distribution": self.result.distribution,
            "failed_sample_ids": self.result.failed_sample_ids,
        }

    def save(self, output_path: str, format: str = "markdown"):
        """Save report to file.

        Args:
            output_path: Output file path
            format: 'markdown' or 'json'
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.to_json(), f, indent=2, ensure_ascii=False)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.to_markdown())

    def print_summary(self):
        """Print summary to console."""
        score = self.result.pass_rate * 100
        if score >= 90:
            grade = "🟢 优秀"
        elif score >= 70:
            grade = "🟡 良好"
        elif score >= 50:
            grade = "🟠 一般"
        else:
            grade = "🔴 需改进"

        print(f"\n{'='*50}")
        print(f"  数据质量检查结果")
        print(f"{'='*50}")
        print(f"  总样本: {self.result.total_samples}")
        print(f"  通过: {self.result.passed_samples}")
        print(f"  失败: {self.result.failed_samples}")
        print(f"  通过率: {self.result.pass_rate:.1%}")
        print(f"  评级: {grade}")
        print(f"{'='*50}\n")
