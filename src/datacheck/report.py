"""Quality report generation."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from datacheck.checker import CheckResult


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
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总样本数 | {self.result.total_samples} |",
            f"| 通过样本 | {self.result.passed_samples} |",
            f"| 失败样本 | {self.result.failed_samples} |",
            f"| **通过率** | **{self.result.pass_rate:.1%}** |",
            "",
        ]

        # Sampling notice
        if self.result.sampled:
            lines.extend([
                f"> **注意**: 本报告基于抽样检查 ({self.result.sampled_count}/{self.result.original_count} 样本)",
                "",
            ])

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

        lines.extend(
            [
                f"### 质量评级: {grade} ({score:.0f}分)",
                "",
            ]
        )

        # Issue summary
        if self.result.error_count or self.result.warning_count:
            lines.extend(
                [
                    "### 问题统计",
                    "",
                    "| 级别 | 数量 |",
                    "|------|------|",
                    f"| 🔴 错误 | {self.result.error_count} |",
                    f"| 🟡 警告 | {self.result.warning_count} |",
                    f"| 🔵 提示 | {self.result.info_count} |",
                    "",
                ]
            )

        # Rule results
        if self.result.rule_results:
            lines.extend(
                [
                    "---",
                    "",
                    "## 规则检查详情",
                    "",
                ]
            )

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
            lines.extend(
                [
                    "---",
                    "",
                    "## 重复检测",
                    "",
                    f"发现 **{len(self.result.duplicates)}** 组重复数据:",
                    "",
                ]
            )

            for i, dup_group in enumerate(self.result.duplicates[:10], 1):
                lines.append(f"{i}. {', '.join(dup_group)}")

            if len(self.result.duplicates) > 10:
                lines.append(f"\n(还有 {len(self.result.duplicates) - 10} 组...)")

            lines.append("")

        # Near-duplicates
        if self.result.near_duplicates:
            lines.extend(
                [
                    "---",
                    "",
                    "## 近似重复检测",
                    "",
                    f"发现 **{len(self.result.near_duplicates)}** 组近似重复数据:",
                    "",
                ]
            )

            for i, dup_group in enumerate(self.result.near_duplicates[:10], 1):
                lines.append(f"{i}. {', '.join(dup_group)}")

            if len(self.result.near_duplicates) > 10:
                lines.append(f"\n(还有 {len(self.result.near_duplicates) - 10} 组...)")

            lines.append("")

        # Distribution
        if self.result.distribution.get("fields"):
            lines.extend(
                [
                    "---",
                    "",
                    "## 数据分布",
                    "",
                ]
            )

            for field_name, field_stats in self.result.distribution["fields"].items():
                lines.append(f"### {field_name}")
                lines.append("")

                if "length_stats" in field_stats:
                    stats = field_stats["length_stats"]
                    lines.append(
                        f"- 长度: 最小 {stats['min']}, 最大 {stats['max']}, 平均 {stats['avg']:.0f}"
                    )

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
            lines.extend(
                [
                    "---",
                    "",
                    "## 与参考数据对比",
                    "",
                    f"样本数量: {comp['sample_count']} vs 参考: {comp['reference_count']}",
                    "",
                ]
            )

            for field_name, field_comp in comp.get("field_comparisons", {}).items():
                if "length_comparison" in field_comp:
                    lc = field_comp["length_comparison"]
                    lines.append(
                        f"- **{field_name}** 平均长度: {lc['sample_avg']:.0f} vs {lc['reference_avg']:.0f} ({lc['diff_percent']:.1f}% 差异)"
                    )

            lines.append("")

        # Failed samples
        if self.result.failed_sample_ids:
            lines.extend(
                [
                    "---",
                    "",
                    "## 失败样本列表",
                    "",
                    f"共 {len(self.result.failed_sample_ids)} 个样本未通过检查:",
                    "",
                ]
            )

            for sid in self.result.failed_sample_ids[:20]:
                lines.append(f"- {sid}")

            if len(self.result.failed_sample_ids) > 20:
                lines.append(f"\n(还有 {len(self.result.failed_sample_ids) - 20} 个...)")

        lines.extend(
            [
                "",
                "---",
                "",
                "> 报告由 DataCheck 自动生成",
            ]
        )

        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate self-contained HTML report with inline CSS."""
        score = self.result.pass_rate * 100
        if score >= 90:
            grade, grade_color = "优秀", "#22c55e"
        elif score >= 70:
            grade, grade_color = "良好", "#eab308"
        elif score >= 50:
            grade, grade_color = "一般", "#f97316"
        else:
            grade, grade_color = "需改进", "#ef4444"

        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build sections
        sampling_html = ""
        if self.result.sampled:
            sampling_html = (
                f'<div class="notice">抽样检查: {self.result.sampled_count}'
                f'/{self.result.original_count} 样本</div>'
            )

        # Issue summary
        issues_html = ""
        if self.result.error_count or self.result.warning_count:
            issues_html = f"""
            <div class="section">
                <h2>问题统计</h2>
                <table>
                    <tr><th>级别</th><th>数量</th></tr>
                    <tr><td class="error">错误</td><td>{self.result.error_count}</td></tr>
                    <tr><td class="warning">警告</td><td>{self.result.warning_count}</td></tr>
                    <tr><td class="info">提示</td><td>{self.result.info_count}</td></tr>
                </table>
            </div>"""

        # Rule results
        rules_html = ""
        if self.result.rule_results:
            rows = ""
            for rule_id, rd in self.result.rule_results.items():
                severity_cls = rd.get("severity", "warning")
                status = "PASS" if rd["failed"] == 0 else "FAIL"
                status_cls = "pass" if rd["failed"] == 0 else "fail"
                total = rd["passed"] + rd["failed"]
                pct = rd["passed"] / total * 100 if total > 0 else 100
                rows += f"""
                    <tr>
                        <td><span class="badge {severity_cls}">{severity_cls}</span></td>
                        <td>{rd['name']}</td>
                        <td>{rd['passed']}/{total}</td>
                        <td>
                            <div class="bar-bg">
                                <div class="bar-fill" style="width:{pct:.0f}%"></div>
                            </div>
                        </td>
                        <td><span class="status {status_cls}">{status}</span></td>
                    </tr>"""
            rules_html = f"""
            <div class="section">
                <h2>规则检查详情</h2>
                <table>
                    <tr><th>级别</th><th>规则</th><th>通过/总数</th><th>通过率</th><th>状态</th></tr>
                    {rows}
                </table>
            </div>"""

        # Duplicates
        dupes_html = ""
        if self.result.duplicates:
            items = "".join(
                f"<li>{', '.join(g)}</li>"
                for g in self.result.duplicates[:10]
            )
            more = (
                f"<p>还有 {len(self.result.duplicates) - 10} 组...</p>"
                if len(self.result.duplicates) > 10 else ""
            )
            dupes_html = f"""
            <div class="section">
                <h2>重复检测 ({len(self.result.duplicates)} 组)</h2>
                <ol>{items}</ol>{more}
            </div>"""

        # Near-duplicates
        near_dupes_html = ""
        if self.result.near_duplicates:
            items = "".join(
                f"<li>{', '.join(g)}</li>"
                for g in self.result.near_duplicates[:10]
            )
            near_dupes_html = f"""
            <div class="section">
                <h2>近似重复 ({len(self.result.near_duplicates)} 组)</h2>
                <ol>{items}</ol>
            </div>"""

        # Distribution
        dist_html = ""
        if self.result.distribution.get("fields"):
            rows = ""
            for fname, fs in self.result.distribution["fields"].items():
                ftype = fs.get("type", "-")
                length_info = ""
                if "length_stats" in fs:
                    s = fs["length_stats"]
                    length_info = f"{s['min']}-{s['max']} (avg {s['avg']:.0f})"
                unique_info = f"{fs['unique_ratio']:.1%}" if "unique_ratio" in fs else "-"
                null_info = str(fs.get("null_count", 0))
                rows += f"""
                    <tr>
                        <td>{fname}</td><td>{ftype}</td>
                        <td>{length_info or '-'}</td>
                        <td>{unique_info}</td><td>{null_info}</td>
                    </tr>"""
            dist_html = f"""
            <div class="section">
                <h2>数据分布</h2>
                <table>
                    <tr><th>字段</th><th>类型</th><th>长度范围</th><th>唯一率</th><th>空值</th></tr>
                    {rows}
                </table>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{self.title}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f8fafc; color:#1e293b; padding:2rem; }}
  .container {{ max-width:900px; margin:0 auto; }}
  h1 {{ font-size:1.5rem; margin-bottom:0.5rem; }}
  .meta {{ color:#64748b; font-size:0.875rem; margin-bottom:1.5rem; }}
  .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:1rem; margin-bottom:1.5rem; }}
  .card {{ background:#fff; border-radius:8px; padding:1rem; box-shadow:0 1px 3px rgba(0,0,0,.1); text-align:center; }}
  .card .value {{ font-size:1.5rem; font-weight:700; }}
  .card .label {{ font-size:0.75rem; color:#64748b; margin-top:0.25rem; }}
  .grade {{ color:{grade_color}; }}
  .notice {{ background:#fffbeb; border-left:4px solid #f59e0b; padding:0.75rem 1rem; margin-bottom:1.5rem; border-radius:0 4px 4px 0; }}
  .section {{ background:#fff; border-radius:8px; padding:1.5rem; margin-bottom:1.5rem; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
  .section h2 {{ font-size:1.1rem; margin-bottom:1rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.875rem; }}
  th,td {{ padding:0.5rem 0.75rem; text-align:left; border-bottom:1px solid #e2e8f0; }}
  th {{ background:#f1f5f9; font-weight:600; }}
  .badge {{ padding:2px 8px; border-radius:10px; font-size:0.75rem; color:#fff; }}
  .badge.error {{ background:#ef4444; }}
  .badge.warning {{ background:#f59e0b; }}
  .badge.info {{ background:#3b82f6; }}
  .status {{ font-weight:600; }}
  .status.pass {{ color:#22c55e; }}
  .status.fail {{ color:#ef4444; }}
  .error {{ color:#ef4444; font-weight:600; }}
  .warning {{ color:#f59e0b; font-weight:600; }}
  .info {{ color:#3b82f6; }}
  .bar-bg {{ background:#e2e8f0; border-radius:4px; height:8px; width:100px; }}
  .bar-fill {{ background:#22c55e; border-radius:4px; height:8px; min-width:2px; }}
  ol {{ padding-left:1.5rem; }}
  li {{ margin-bottom:0.25rem; }}
  .footer {{ text-align:center; color:#94a3b8; font-size:0.75rem; margin-top:2rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>{self.title}</h1>
  <div class="meta">生成时间: {generated_at}</div>

  <div class="summary">
    <div class="card"><div class="value">{self.result.total_samples}</div><div class="label">总样本</div></div>
    <div class="card"><div class="value">{self.result.passed_samples}</div><div class="label">通过</div></div>
    <div class="card"><div class="value">{self.result.failed_samples}</div><div class="label">失败</div></div>
    <div class="card"><div class="value grade">{self.result.pass_rate:.1%}</div><div class="label">通过率</div></div>
    <div class="card"><div class="value grade">{grade}</div><div class="label">评级</div></div>
  </div>

  {sampling_html}
  {issues_html}
  {rules_html}
  {dupes_html}
  {near_dupes_html}
  {dist_html}

  <div class="footer">报告由 DataCheck 自动生成</div>
</div>
</body>
</html>"""

    def to_json(self) -> Dict[str, Any]:
        """Generate JSON report."""
        summary = {
            "total_samples": self.result.total_samples,
            "passed_samples": self.result.passed_samples,
            "failed_samples": self.result.failed_samples,
            "pass_rate": self.result.pass_rate,
            "error_count": self.result.error_count,
            "warning_count": self.result.warning_count,
            "info_count": self.result.info_count,
        }

        if self.result.sampled:
            summary["sampling"] = {
                "enabled": True,
                "sampled_count": self.result.sampled_count,
                "original_count": self.result.original_count,
            }

        return {
            "title": self.title,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "rule_results": self.result.rule_results,
            "duplicates": self.result.duplicates,
            "near_duplicates": self.result.near_duplicates,
            "distribution": self.result.distribution,
            "failed_sample_ids": self.result.failed_sample_ids,
        }

    def save(self, output_path: str, format: str = "markdown"):
        """Save report to file.

        Args:
            output_path: Output file path
            format: 'markdown', 'json', or 'html'
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.to_json(), f, indent=2, ensure_ascii=False)
        elif format == "html":
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.to_html())
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

        print(f"\n{'=' * 50}")
        print("  数据质量检查结果")
        print(f"{'=' * 50}")
        print(f"  总样本: {self.result.total_samples}")
        print(f"  通过: {self.result.passed_samples}")
        print(f"  失败: {self.result.failed_samples}")
        print(f"  通过率: {self.result.pass_rate:.1%}")
        print(f"  评级: {grade}")
        print(f"{'=' * 50}\n")
