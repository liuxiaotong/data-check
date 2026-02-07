"""DataCheck CLI - 命令行界面."""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from datacheck import __version__
from datacheck.checker import DataChecker
from datacheck.report import QualityReport
from datacheck.rules import RuleSet, get_sft_ruleset, get_preference_ruleset


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
    "-f", "--format", type=click.Choice(["markdown", "json"]), default="markdown", help="报告格式"
)
@click.option(
    "--ruleset",
    type=click.Choice(["default", "sft", "preference"]),
    default="default",
    help="规则集",
)
def check(
    data_path: str,
    schema: Optional[str],
    output: Optional[str],
    format: str,
    ruleset: str,
):
    """检查数据文件质量

    DATA_PATH: 数据 JSON 文件路径
    """
    # Select ruleset
    if ruleset == "sft":
        rules = get_sft_ruleset()
    elif ruleset == "preference":
        rules = get_preference_ruleset()
    else:
        rules = RuleSet()

    checker = DataChecker(rules)

    click.echo(f"正在检查 {data_path}...")

    result = checker.check_file(data_path, schema)

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

    # Show issues
    if result.error_count > 0:
        click.echo(f"🔴 错误: {result.error_count}")
    if result.warning_count > 0:
        click.echo(f"🟡 警告: {result.warning_count}")
    if result.duplicates:
        click.echo(f"⚠️  重复: {len(result.duplicates)} 组")

    # Exit with error if pass rate is too low
    if result.pass_rate < 0.5:
        sys.exit(1)


@main.command()
@click.argument("analysis_dir", type=click.Path(exists=True))
@click.option(
    "-d", "--data", type=click.Path(exists=True), help="数据文件路径 (默认: 合成数据或样例数据)"
)
@click.option("-o", "--output", type=click.Path(), help="报告输出路径")
@click.option(
    "-f", "--format", type=click.Choice(["markdown", "json"]), default="markdown", help="报告格式"
)
def validate(
    analysis_dir: str,
    data: Optional[str],
    output: Optional[str],
    format: str,
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
        ext = "md" if format == "markdown" else "json"
        output = output_dir / f"quality_report.{ext}"

    report.save(str(output), format)
    click.echo(f"✓ 报告已保存: {output}")

    # Print summary
    report.print_summary()


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
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        samples = data.get("samples", data.get("responses", data if isinstance(data, list) else []))

        checker = DataChecker()
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


if __name__ == "__main__":
    main()
