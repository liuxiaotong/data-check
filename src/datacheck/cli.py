"""DataCheck CLI - 命令行界面."""

import sys
from pathlib import Path
from typing import Optional

import click

from datacheck import __version__
from datacheck.checker import DataChecker
from datacheck.report import QualityReport
from datacheck.rules import RuleSet, get_sft_ruleset, get_preference_ruleset, get_llm_ruleset


@click.group()
@click.version_option(version=__version__, prog_name="datacheck")
def main():
    """DataCheck - 数据质检工具

    自动化质量检查、异常检测、分布分析。
    """
    pass


@main.command()
@click.argument("data_path", type=click.Path(exists=True))
@click.option("-s", "--schema", type=click.Path(exists=True), help="Schema 文件路径")
@click.option("-o", "--output", type=click.Path(), help="报告输出路径")
@click.option(
    "-f", "--format",
    type=click.Choice(["markdown", "json", "html"]), default="markdown", help="报告格式",
)
@click.option(
    "--ruleset",
    type=click.Choice(["default", "sft", "preference", "llm"]),
    default="default",
    help="规则集 (llm 需要 pip install knowlyr-datacheck[llm])",
)
@click.option("--rules-file", type=click.Path(exists=True), default=None, help="自定义规则配置文件 (YAML)")
@click.option("--sample", type=int, default=None, help="随机抽样数量")
@click.option("--sample-rate", type=float, default=None, help="随机抽样比例 (0-1)")
@click.option("--threshold", type=float, default=0.5, show_default=True, help="最低通过率阈值，低于此值退出码为 1")
@click.option("--strict", is_flag=True, default=False, help="严格模式: 任何错误或警告都返回退出码 1")
def check(
    data_path: str,
    schema: Optional[str],
    output: Optional[str],
    format: str,
    ruleset: str,
    rules_file: Optional[str],
    sample: Optional[int],
    sample_rate: Optional[float],
    threshold: float,
    strict: bool,
):
    """检查数据文件质量

    DATA_PATH: 数据文件路径 (JSON/JSONL/CSV)
    """
    # Select ruleset
    if rules_file:
        rules = RuleSet.from_config(rules_file)
    elif ruleset == "sft":
        rules = get_sft_ruleset()
    elif ruleset == "preference":
        rules = get_preference_ruleset()
    elif ruleset == "llm":
        rules = get_llm_ruleset()
    else:
        rules = RuleSet()

    checker = DataChecker(rules)

    click.echo(f"正在检查 {data_path}...")

    # Progress callback - shows progress bar for large datasets
    progress_bar = [None]  # mutable container for closure

    def on_progress(current, total):
        if progress_bar[0] is None:
            if total > 100:
                progress_bar[0] = click.progressbar(
                    length=total, label="检查进度", file=sys.stderr,
                )
                progress_bar[0].__enter__()
            else:
                return
        progress_bar[0].update(1)

    try:
        result = checker.check_file(
            data_path, schema, sample_count=sample, sample_rate=sample_rate,
            on_progress=on_progress,
        )
    finally:
        if progress_bar[0] is not None:
            progress_bar[0].__exit__(None, None, None)

    if not result.success:
        click.echo(f"✗ 检查失败: {result.error}", err=True)
        sys.exit(1)

    # Generate report
    report = QualityReport(result)

    if output:
        report.save(output, format)
        click.echo(f"✓ 报告已保存: {output}")

    # Print summary
    report.print_summary()

    # Show sampling notice
    if result.sampled:
        click.echo(f"  抽样检查: {result.sampled_count}/{result.original_count} 样本")

    # Show issues
    if result.error_count > 0:
        click.echo(f"🔴 错误: {result.error_count}")
    if result.warning_count > 0:
        click.echo(f"🟡 警告: {result.warning_count}")
    if result.duplicates:
        click.echo(f"⚠️  重复: {len(result.duplicates)} 组")

    # Exit with error based on threshold / strict mode
    if strict and (result.error_count > 0 or result.warning_count > 0):
        click.echo("严格模式: 检测到错误或警告，退出码 1")
        sys.exit(1)
    if result.pass_rate < threshold:
        click.echo(f"通过率 {result.pass_rate:.1%} 低于阈值 {threshold:.1%}，退出码 1")
        sys.exit(1)


@main.command()
@click.argument("analysis_dir", type=click.Path(exists=True))
@click.option(
    "-d", "--data", type=click.Path(exists=True), help="数据文件路径 (默认: 合成数据或样例数据)"
)
@click.option("-o", "--output", type=click.Path(), help="报告输出路径")
@click.option(
    "-f", "--format", type=click.Choice(["markdown", "json", "html"]), default="markdown", help="报告格式"
)
@click.option("--threshold", type=float, default=0.5, show_default=True, help="最低通过率阈值，低于此值退出码为 1")
@click.option("--strict", is_flag=True, default=False, help="严格模式: 任何错误或警告都返回退出码 1")
def validate(
    analysis_dir: str,
    data: Optional[str],
    output: Optional[str],
    format: str,
    threshold: float,
    strict: bool,
):
    """使用 DataRecipe 分析结果验证数据

    ANALYSIS_DIR: DataRecipe 分析输出目录
    """
    checker = DataChecker()

    click.echo(f"正在验证 {analysis_dir}...")

    result = checker.check_from_datarecipe(analysis_dir, data)

    if not result.success:
        click.echo(f"✗ 验证失败: {result.error}", err=True)
        sys.exit(1)

    # Generate report
    report = QualityReport(result, title="数据验证报告")

    # Default output path
    if output is None:
        output_dir = Path(analysis_dir) / "12_质检报告"
        output_dir.mkdir(exist_ok=True)
        ext = {"markdown": "md", "json": "json", "html": "html"}[format]
        output = output_dir / f"quality_report.{ext}"

    report.save(str(output), format)
    click.echo(f"✓ 报告已保存: {output}")

    # Print summary
    report.print_summary()

    # Exit with error based on threshold / strict mode
    if strict and (result.error_count > 0 or result.warning_count > 0):
        click.echo("严格模式: 检测到错误或警告，退出码 1")
        sys.exit(1)
    if result.pass_rate < threshold:
        click.echo(f"通过率 {result.pass_rate:.1%} 低于阈值 {threshold:.1%}，退出码 1")
        sys.exit(1)


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("-o", "--output", type=click.Path(), help="对比报告输出路径")
def compare(files: tuple, output: Optional[str]):
    """对比多个数据文件的分布

    FILES: 要对比的数据文件
    """
    if len(files) < 2:
        click.echo("错误: 至少需要 2 个文件", err=True)
        sys.exit(1)

    click.echo(f"正在对比 {len(files)} 个文件...")

    distributions = []

    for file_path in files:
        checker = DataChecker()
        samples, _ = checker._load_data(Path(file_path))
        result = checker.check(samples, {})

        distributions.append(
            {
                "file": str(file_path),
                "sample_count": len(samples),
                "distribution": result.distribution,
            }
        )

    # Build comparison report
    report_lines = [
        "# 数据分布对比报告",
        "",
        "## 文件概要",
        "",
        "| 文件 | 样本数 |",
        "|------|--------|",
    ]

    for dist in distributions:
        report_lines.append(f"| {Path(dist['file']).name} | {dist['sample_count']} |")

    report_lines.extend(["", "## 字段对比", ""])

    # Collect all fields
    all_fields = set()
    for dist in distributions:
        all_fields.update(dist["distribution"].get("fields", {}).keys())

    for field in sorted(all_fields):
        report_lines.append(f"### {field}")
        report_lines.append("")

        for dist in distributions:
            field_data = dist["distribution"].get("fields", {}).get(field, {})
            file_name = Path(dist["file"]).name

            if "length_stats" in field_data:
                stats = field_data["length_stats"]
                report_lines.append(
                    f"- **{file_name}**: 长度 {stats['min']}-{stats['max']} (平均 {stats['avg']:.0f})"
                )
            elif "value_stats" in field_data:
                stats = field_data["value_stats"]
                report_lines.append(
                    f"- **{file_name}**: 值 {stats['min']}-{stats['max']} (平均 {stats['avg']:.1f})"
                )

        report_lines.append("")

    report_content = "\n".join(report_lines)

    if output:
        Path(output).write_text(report_content, encoding="utf-8")
        click.echo(f"✓ 对比报告已保存: {output}")
    else:
        click.echo(report_content)


@main.command()
def rules():
    """列出所有可用的检查规则"""
    ruleset = RuleSet()

    click.echo("\n可用规则:")
    click.echo("=" * 50)

    for rule in ruleset.rules.values():
        status = "✓" if rule.enabled else "✗"
        severity_icon = {
            "error": "🔴",
            "warning": "🟡",
            "info": "🔵",
        }.get(rule.severity.value, "⚪")

        click.echo(f"\n{status} [{rule.id}] {rule.name} {severity_icon}")
        click.echo(f"   {rule.description}")

    click.echo("\n" + "=" * 50)
    click.echo("\n预设规则集:")
    click.echo("  - default: 通用规则")
    click.echo("  - sft: SFT 数据规则")
    click.echo("  - preference: 偏好数据规则")


@main.command()
@click.argument("data_path", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Schema 输出路径 (JSON)")
def infer(data_path: str, output: Optional[str]):
    """从数据文件推断 Schema

    DATA_PATH: 数据文件路径 (JSON/JSONL/CSV)
    """
    checker = DataChecker()

    click.echo(f"正在推断 {data_path} 的 Schema...")

    schema = checker.infer_schema_file(data_path, output)

    field_count = len(schema.get("fields", {}))
    required_count = sum(1 for f in schema.get("fields", {}).values() if f.get("required"))

    click.echo(f"✓ 推断完成: {field_count} 个字段, {required_count} 个必填")

    if output:
        click.echo(f"  Schema 已保存: {output}")
    else:
        import json
        click.echo(json.dumps(schema, indent=2, ensure_ascii=False))


@main.command()
@click.argument("data_path", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), required=True, help="修复后文件输出路径 (JSONL)")
@click.option("--no-dedup", is_flag=True, default=False, help="不去除重复")
@click.option("--no-trim", is_flag=True, default=False, help="不去除空白")
@click.option("--strip-pii", is_flag=True, default=False, help="脱敏 PII 信息")
def fix(data_path: str, output: str, no_dedup: bool, no_trim: bool, strip_pii: bool):
    """修复数据文件常见质量问题

    DATA_PATH: 数据文件路径 (JSON/JSONL/CSV)
    """
    from datacheck.fixer import DataFixer

    fixer = DataFixer()

    click.echo(f"正在修复 {data_path}...")

    result = fixer.fix_file(
        data_path, output,
        dedup=not no_dedup,
        trim=not no_trim,
        strip_pii=strip_pii,
    )

    click.echo(f"✓ 修复完成: {result.total_input} → {result.total_output} 样本")
    if result.duplicates_removed:
        click.echo(f"  去除重复: {result.duplicates_removed}")
    if result.trimmed_count:
        click.echo(f"  修剪空白: {result.trimmed_count} 个字段")
    if result.empty_removed:
        click.echo(f"  移除空样本: {result.empty_removed}")
    if result.pii_redacted_count:
        click.echo(f"  PII 脱敏: {result.pii_redacted_count} 个字段")
    click.echo(f"  输出文件: {output}")


@main.command(name="diff")
@click.argument("report_a", type=click.Path(exists=True))
@click.argument("report_b", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="对比报告输出路径")
def diff_cmd(report_a: str, report_b: str, output: Optional[str]):
    """对比两份质量报告

    REPORT_A: 第一份报告 (JSON 格式)
    REPORT_B: 第二份报告 (JSON 格式)
    """
    import json as json_module

    with open(report_a, "r", encoding="utf-8") as f:
        data_a = json_module.load(f)
    with open(report_b, "r", encoding="utf-8") as f:
        data_b = json_module.load(f)

    diff_report = QualityReport.diff(data_a, data_b)

    if output:
        Path(output).write_text(diff_report, encoding="utf-8")
        click.echo(f"✓ 对比报告已保存: {output}")
    else:
        click.echo(diff_report)


if __name__ == "__main__":
    main()
