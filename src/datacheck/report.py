"""Quality report generation."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from datacheck.checker import BatchCheckResult, CheckResult


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

    @staticmethod
    def diff(report_a: Dict[str, Any], report_b: Dict[str, Any]) -> str:
        """Compare two JSON reports and return a markdown diff.

        Args:
            report_a: First report (JSON dict, "before")
            report_b: Second report (JSON dict, "after")

        Returns:
            Markdown formatted comparison
        """
        def _arrow(old, new):
            if new > old:
                return "↑"
            elif new < old:
                return "↓"
            return "="

        def _fmt_pct(val):
            if isinstance(val, (int, float)):
                return f"{val:.1%}" if val <= 1 else f"{val}"
            return str(val)

        sa = report_a.get("summary", {})
        sb = report_b.get("summary", {})

        lines = [
            "# 质量报告对比",
            "",
            f"- A: {report_a.get('title', '报告 A')} ({report_a.get('generated_at', '-')})",
            f"- B: {report_b.get('title', '报告 B')} ({report_b.get('generated_at', '-')})",
            "",
            "## 概要对比",
            "",
            "| 指标 | A | B | 变化 |",
            "|------|---|---|------|",
        ]

        metrics = [
            ("总样本", "total_samples", str),
            ("通过样本", "passed_samples", str),
            ("失败样本", "failed_samples", str),
            ("通过率", "pass_rate", _fmt_pct),
            ("错误数", "error_count", str),
            ("警告数", "warning_count", str),
        ]

        for label, key, fmt in metrics:
            va = sa.get(key, 0)
            vb = sb.get(key, 0)
            arrow = _arrow(va, vb)
            lines.append(f"| {label} | {fmt(va)} | {fmt(vb)} | {arrow} |")

        # Rule comparison
        rules_a = report_a.get("rule_results", {})
        rules_b = report_b.get("rule_results", {})
        all_rules = sorted(set(rules_a.keys()) | set(rules_b.keys()))

        if all_rules:
            lines.extend([
                "",
                "## 规则对比",
                "",
                "| 规则 | A 失败 | B 失败 | 变化 |",
                "|------|--------|--------|------|",
            ])

            for rid in all_rules:
                ra = rules_a.get(rid, {})
                rb = rules_b.get(rid, {})
                name = rb.get("name", ra.get("name", rid))
                fa = ra.get("failed", 0)
                fb = rb.get("failed", 0)
                arrow = _arrow(fa, fb)
                lines.append(f"| {name} | {fa} | {fb} | {arrow} |")

        # Duplicates comparison
        dupes_a = len(report_a.get("duplicates", []))
        dupes_b = len(report_b.get("duplicates", []))
        if dupes_a or dupes_b:
            lines.extend([
                "",
                "## 重复数据",
                "",
                f"- A: {dupes_a} 组",
                f"- B: {dupes_b} 组 {_arrow(dupes_a, dupes_b)}",
            ])

        return "\n".join(lines)


def _grade(pass_rate: float):
    """Return (grade_text, grade_color) for a pass rate."""
    score = pass_rate * 100
    if score >= 90:
        return "🟢 优秀", "#22c55e"
    elif score >= 70:
        return "🟡 良好", "#eab308"
    elif score >= 50:
        return "🟠 一般", "#f97316"
    return "🔴 需改进", "#ef4444"


@dataclass
class BatchQualityReport:
    """Generate quality reports for batch directory checks."""

    result: BatchCheckResult
    title: str = "批量数据质量报告"

    def to_markdown(self) -> str:
        """Generate markdown report."""
        r = self.result
        grade_text, _ = _grade(r.overall_pass_rate)

        lines = [
            f"# {self.title}",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"目录: `{r.directory}`",
            "",
            "---",
            "",
            "## 汇总",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 检查文件数 | {r.total_files} |",
            f"| 总样本数 | {r.total_samples} |",
            f"| 通过样本 | {r.total_passed_samples} |",
            f"| 失败样本 | {r.total_failed_samples} |",
            f"| **总通过率** | **{r.overall_pass_rate:.1%}** |",
            "",
            f"### 质量评级: {grade_text} ({r.overall_pass_rate * 100:.0f}分)",
            "",
        ]

        if r.file_results:
            lines.extend([
                "---",
                "",
                "## 文件明细",
                "",
                "| 文件 | 样本数 | 通过率 | 错误 | 警告 | 状态 |",
                "|------|--------|--------|------|------|------|",
            ])
            for path, fr in r.file_results.items():
                status = "✅" if fr.error_count == 0 else "❌"
                lines.append(
                    f"| {path} | {fr.total_samples} | {fr.pass_rate:.1%} "
                    f"| {fr.error_count} | {fr.warning_count} | {status} |"
                )
            lines.append("")

        if r.skipped_files:
            lines.extend(["---", "", "## 跳过文件", ""])
            for s in r.skipped_files:
                lines.append(f"- {s}")
            lines.append("")

        lines.extend(["", "---", "", "> 报告由 DataCheck 自动生成"])
        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate self-contained HTML report."""
        r = self.result
        grade_text, grade_color = _grade(r.overall_pass_rate)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        file_rows = ""
        for path, fr in r.file_results.items():
            status = "PASS" if fr.error_count == 0 else "FAIL"
            status_cls = "pass" if fr.error_count == 0 else "fail"
            file_rows += (
                f"<tr><td>{path}</td><td>{fr.total_samples}</td>"
                f"<td>{fr.pass_rate:.1%}</td><td>{fr.error_count}</td>"
                f"<td>{fr.warning_count}</td>"
                f'<td><span class="status {status_cls}">{status}</span></td></tr>'
            )

        skipped_html = ""
        if r.skipped_files:
            items = "".join(f"<li>{s}</li>" for s in r.skipped_files)
            skipped_html = f'<div class="section"><h2>跳过文件 ({len(r.skipped_files)})</h2><ul>{items}</ul></div>'

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{self.title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8fafc;color:#1e293b;padding:2rem}}
  .container{{max-width:960px;margin:0 auto}}
  h1{{font-size:1.5rem;margin-bottom:.5rem}}
  .meta{{color:#64748b;font-size:.875rem;margin-bottom:1.5rem}}
  .summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:1.5rem}}
  .card{{background:#fff;border-radius:8px;padding:1rem;box-shadow:0 1px 3px rgba(0,0,0,.1);text-align:center}}
  .card .value{{font-size:1.5rem;font-weight:700}} .card .label{{font-size:.75rem;color:#64748b;margin-top:.25rem}}
  .grade{{color:{grade_color}}}
  .section{{background:#fff;border-radius:8px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  .section h2{{font-size:1.1rem;margin-bottom:1rem}}
  table{{width:100%;border-collapse:collapse;font-size:.875rem}}
  th,td{{padding:.5rem .75rem;text-align:left;border-bottom:1px solid #e2e8f0}}
  th{{background:#f1f5f9;font-weight:600}}
  .status{{font-weight:600}} .status.pass{{color:#22c55e}} .status.fail{{color:#ef4444}}
  ul{{padding-left:1.5rem}} li{{margin-bottom:.25rem}}
  .footer{{text-align:center;color:#94a3b8;font-size:.75rem;margin-top:2rem}}
</style>
</head>
<body>
<div class="container">
  <h1>{self.title}</h1>
  <div class="meta">生成时间: {generated_at} &middot; 目录: {r.directory}</div>
  <div class="summary">
    <div class="card"><div class="value">{r.total_files}</div><div class="label">文件数</div></div>
    <div class="card"><div class="value">{r.total_samples}</div><div class="label">总样本</div></div>
    <div class="card"><div class="value">{r.total_passed_samples}</div><div class="label">通过</div></div>
    <div class="card"><div class="value">{r.total_failed_samples}</div><div class="label">失败</div></div>
    <div class="card"><div class="value grade">{r.overall_pass_rate:.1%}</div><div class="label">通过率</div></div>
    <div class="card"><div class="value grade">{grade_text.split()[-1]}</div><div class="label">评级</div></div>
  </div>
  <div class="section">
    <h2>文件明细</h2>
    <table>
      <tr><th>文件</th><th>样本数</th><th>通过率</th><th>错误</th><th>警告</th><th>状态</th></tr>
      {file_rows}
    </table>
  </div>
  {skipped_html}
  <div class="footer">报告由 DataCheck 自动生成</div>
</div>
</body>
</html>"""

    def to_json(self) -> Dict[str, Any]:
        """Generate JSON report."""
        r = self.result
        files = {}
        for path, fr in r.file_results.items():
            files[path] = {
                "summary": {
                    "total_samples": fr.total_samples,
                    "passed_samples": fr.passed_samples,
                    "failed_samples": fr.failed_samples,
                    "pass_rate": fr.pass_rate,
                    "error_count": fr.error_count,
                    "warning_count": fr.warning_count,
                },
                "rule_results": fr.rule_results,
                "duplicates": fr.duplicates,
            }
        return {
            "title": self.title,
            "generated_at": datetime.now().isoformat(),
            "aggregate": {
                "total_files": r.total_files,
                "passed_files": r.passed_files,
                "failed_files": r.failed_files,
                "total_samples": r.total_samples,
                "total_passed_samples": r.total_passed_samples,
                "total_failed_samples": r.total_failed_samples,
                "overall_pass_rate": r.overall_pass_rate,
                "total_error_count": r.total_error_count,
                "total_warning_count": r.total_warning_count,
            },
            "files": files,
            "skipped_files": r.skipped_files,
        }

    def save(self, output_path: str, format: str = "markdown"):
        """Save report to file."""
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
        r = self.result
        grade_text, _ = _grade(r.overall_pass_rate)
        print(f"\n{'=' * 50}")
        print("  批量数据质量检查结果")
        print(f"{'=' * 50}")
        print(f"  文件数: {r.total_files}")
        print(f"  总样本: {r.total_samples}")
        print(f"  通过: {r.total_passed_samples}")
        print(f"  失败: {r.total_failed_samples}")
        print(f"  通过率: {r.overall_pass_rate:.1%}")
        print(f"  评级: {grade_text}")
        print(f"{'=' * 50}\n")
