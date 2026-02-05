"""DataCheck MCP Server - Model Context Protocol 服务."""

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from datacheck.checker import DataChecker
from datacheck.report import QualityReport
from datacheck.rules import RuleSet, get_sft_ruleset, get_preference_ruleset


def create_server() -> "Server":
    """创建 MCP 服务器实例."""
    if not HAS_MCP:
        raise ImportError("MCP 未安装。请运行: pip install datacheck[mcp]")

    server = Server("datacheck")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """列出可用的工具."""
        return [
            Tool(
                name="check_data_quality",
                description="检查数据文件的质量",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据 JSON 文件路径",
                        },
                        "schema_path": {
                            "type": "string",
                            "description": "Schema 文件路径（可选）",
                        },
                        "ruleset": {
                            "type": "string",
                            "enum": ["default", "sft", "preference"],
                            "description": "规则集（默认: default）",
                        },
                    },
                    "required": ["data_path"],
                },
            ),
            Tool(
                name="validate_from_datarecipe",
                description="使用 DataRecipe 分析结果验证数据",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "analysis_dir": {
                            "type": "string",
                            "description": "DataRecipe 分析输出目录",
                        },
                        "data_path": {
                            "type": "string",
                            "description": "要验证的数据文件（可选，默认验证合成数据）",
                        },
                    },
                    "required": ["analysis_dir"],
                },
            ),
            Tool(
                name="compare_distributions",
                description="对比多个数据文件的分布",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要对比的数据文件路径列表",
                        },
                    },
                    "required": ["file_paths"],
                },
            ),
            Tool(
                name="list_quality_rules",
                description="列出所有可用的质量检查规则",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """调用工具."""

        if name == "check_data_quality":
            ruleset_name = arguments.get("ruleset", "default")
            if ruleset_name == "sft":
                rules = get_sft_ruleset()
            elif ruleset_name == "preference":
                rules = get_preference_ruleset()
            else:
                rules = RuleSet()

            checker = DataChecker(rules)
            result = checker.check_file(
                arguments["data_path"],
                arguments.get("schema_path"),
            )

            if not result.success:
                return [TextContent(type="text", text=f"检查失败: {result.error}")]

            # Generate summary
            score = result.pass_rate * 100
            if score >= 90:
                grade = "🟢 优秀"
            elif score >= 70:
                grade = "🟡 良好"
            elif score >= 50:
                grade = "🟠 一般"
            else:
                grade = "🔴 需改进"

            summary = f"""## 数据质量检查结果

### 概要
- 总样本: {result.total_samples}
- 通过: {result.passed_samples}
- 失败: {result.failed_samples}
- **通过率: {result.pass_rate:.1%}**
- **评级: {grade}**

### 问题统计
- 🔴 错误: {result.error_count}
- 🟡 警告: {result.warning_count}
- 🔵 提示: {result.info_count}
"""

            if result.duplicates:
                summary += f"\n### 重复检测\n发现 {len(result.duplicates)} 组重复数据\n"

            if result.failed_sample_ids:
                summary += f"\n### 失败样本\n{', '.join(result.failed_sample_ids[:10])}"
                if len(result.failed_sample_ids) > 10:
                    summary += f" (还有 {len(result.failed_sample_ids) - 10} 个...)"

            return [TextContent(type="text", text=summary)]

        elif name == "validate_from_datarecipe":
            checker = DataChecker()
            result = checker.check_from_datarecipe(
                arguments["analysis_dir"],
                arguments.get("data_path"),
            )

            if not result.success:
                return [TextContent(type="text", text=f"验证失败: {result.error}")]

            report = QualityReport(result, title="数据验证报告")

            # Save report
            output_dir = Path(arguments["analysis_dir"]) / "12_质检报告"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "quality_report.md"
            report.save(str(output_path), "markdown")

            # Return summary
            score = result.pass_rate * 100
            grade = "🟢 优秀" if score >= 90 else "🟡 良好" if score >= 70 else "🟠 一般" if score >= 50 else "🔴 需改进"

            return [TextContent(
                type="text",
                text=f"""## 数据验证完成

### 结果
- 通过率: **{result.pass_rate:.1%}**
- 评级: **{grade}**
- 总样本: {result.total_samples}
- 错误: {result.error_count}, 警告: {result.warning_count}

### 报告
已保存到: {output_path}

{"### 重复数据" + chr(10) + f"发现 {len(result.duplicates)} 组重复" if result.duplicates else ""}
"""
            )]

        elif name == "compare_distributions":
            file_paths = arguments["file_paths"]

            if len(file_paths) < 2:
                return [TextContent(type="text", text="错误: 至少需要 2 个文件")]

            distributions = []
            for file_path in file_paths:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                samples = data.get("samples", data.get("responses", data if isinstance(data, list) else []))
                checker = DataChecker()
                result = checker.check(samples, {})

                distributions.append({
                    "file": Path(file_path).name,
                    "count": len(samples),
                    "dist": result.distribution,
                })

            # Build comparison
            lines = ["## 数据分布对比", ""]
            lines.append("| 文件 | 样本数 |")
            lines.append("|------|--------|")
            for d in distributions:
                lines.append(f"| {d['file']} | {d['count']} |")

            lines.extend(["", "### 字段统计", ""])

            all_fields = set()
            for d in distributions:
                all_fields.update(d["dist"].get("fields", {}).keys())

            for field in sorted(all_fields):
                lines.append(f"**{field}**:")
                for d in distributions:
                    field_data = d["dist"].get("fields", {}).get(field, {})
                    if "length_stats" in field_data:
                        stats = field_data["length_stats"]
                        lines.append(f"- {d['file']}: 长度 {stats['avg']:.0f} (avg)")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "list_quality_rules":
            ruleset = RuleSet()
            lines = ["## 可用质量检查规则", ""]

            for rule in ruleset.rules.values():
                severity_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(rule.severity.value, "⚪")
                status = "✓" if rule.enabled else "✗"
                lines.append(f"- {status} **{rule.name}** {severity_icon}")
                lines.append(f"  - ID: `{rule.id}`")
                lines.append(f"  - {rule.description}")
                lines.append("")

            lines.extend([
                "## 预设规则集",
                "- `default`: 通用规则",
                "- `sft`: SFT 数据规则",
                "- `preference`: 偏好数据规则",
            ])

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]

    return server


async def serve():
    """启动 MCP 服务器."""
    if not HAS_MCP:
        raise ImportError("MCP 未安装。请运行: pip install datacheck[mcp]")

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


def main():
    """主入口."""
    import asyncio
    asyncio.run(serve())


if __name__ == "__main__":
    main()
