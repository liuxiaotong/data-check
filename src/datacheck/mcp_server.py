"""DataCheck MCP Server - Model Context Protocol 服务."""

import math
from collections import Counter
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
from datacheck.fixer import DataFixer
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
                description="检查数据文件的质量 (支持 JSON/JSONL/CSV)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据文件路径 (JSON/JSONL/CSV)",
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
                        "sample_count": {
                            "type": "integer",
                            "description": "随机抽样数量（可选）",
                        },
                        "sample_rate": {
                            "type": "number",
                            "description": "随机抽样比例 0-1（可选）",
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
                description="对比多个数据文件的分布 (支持 JSON/JSONL/CSV)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要对比的数据文件路径列表 (JSON/JSONL/CSV)",
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
            Tool(
                name="infer_schema",
                description="从数据文件推断 Schema (字段类型、约束、必填项)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据文件路径 (JSON/JSONL/CSV)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Schema 输出路径（可选）",
                        },
                    },
                    "required": ["data_path"],
                },
            ),
            Tool(
                name="fix_data",
                description="修复数据文件常见质量问题 (去重、去空白、PII 脱敏)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据文件路径 (JSON/JSONL/CSV)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "修复后文件输出路径 (JSONL)",
                        },
                        "strip_pii": {
                            "type": "boolean",
                            "description": "是否脱敏 PII 信息（默认: false）",
                        },
                    },
                    "required": ["data_path", "output_path"],
                },
            ),
            Tool(
                name="batch_check_directory",
                description="批量检查目录下所有数据文件的质量 (递归扫描 JSON/JSONL/CSV)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "要检查的目录路径",
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
                        "pattern": {
                            "type": "string",
                            "description": "文件匹配模式，逗号分隔（默认: *.json,*.jsonl,*.csv）",
                        },
                        "sample_count": {
                            "type": "integer",
                            "description": "每个文件的随机抽样数量（可选）",
                        },
                    },
                    "required": ["directory"],
                },
            ),
            Tool(
                name="check_drift",
                description="检测两个数据文件之间的分布漂移（数值统计差异、类别分布变化、文本特征对比）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path_a": {
                            "type": "string",
                            "description": "数据文件 A 路径 (JSON/JSONL/CSV)",
                        },
                        "data_path_b": {
                            "type": "string",
                            "description": "数据文件 B 路径 (JSON/JSONL/CSV)",
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要对比的字段列表（可选，默认对比所有共有字段）",
                        },
                    },
                    "required": ["data_path_a", "data_path_b"],
                },
            ),
            Tool(
                name="check_leakage",
                description="检测训练集和测试集之间的数据泄漏（完全重复 + token Jaccard 近似重复）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "train_path": {
                            "type": "string",
                            "description": "训练集文件路径 (JSON/JSONL/CSV)",
                        },
                        "test_path": {
                            "type": "string",
                            "description": "测试集文件路径 (JSON/JSONL/CSV)",
                        },
                        "key_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "用于比较的字段（可选，自动检测文本字段）",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "近似重复的 Jaccard 相似度阈值（默认 0.9）",
                            "default": 0.9,
                        },
                    },
                    "required": ["train_path", "test_path"],
                },
            ),
            Tool(
                name="check_bias",
                description="检测数据集偏差（类别不均衡、文本长度分布偏差、语言分布偏差）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据文件路径 (JSON/JSONL/CSV)",
                        },
                        "label_field": {
                            "type": "string",
                            "description": "标签字段名（可选，自动检测）",
                        },
                        "text_field": {
                            "type": "string",
                            "description": "文本字段名（可选，自动检测）",
                        },
                        "dimensions": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["category", "length", "language", "all"],
                            },
                            "description": "检测维度（默认 all）",
                            "default": ["all"],
                        },
                    },
                    "required": ["data_path"],
                },
            ),
            Tool(
                name="check_coverage",
                description="检测数据集覆盖度 — 统计字段完整度、缺失值比例、唯一值分布",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_path": {
                            "type": "string",
                            "description": "数据文件路径 (JSON/JSONL/CSV)",
                        },
                        "sample_count": {
                            "type": "integer",
                            "description": "采样数量（可选，默认全量检测）",
                        },
                    },
                    "required": ["data_path"],
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
                sample_count=arguments.get("sample_count"),
                sample_rate=arguments.get("sample_rate"),
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
            grade = (
                "🟢 优秀"
                if score >= 90
                else "🟡 良好"
                if score >= 70
                else "🟠 一般"
                if score >= 50
                else "🔴 需改进"
            )

            return [
                TextContent(
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
""",
                )
            ]

        elif name == "compare_distributions":
            file_paths = arguments["file_paths"]

            if len(file_paths) < 2:
                return [TextContent(type="text", text="错误: 至少需要 2 个文件")]

            distributions = []
            for file_path in file_paths:
                checker = DataChecker()
                samples, _ = checker._load_data(Path(file_path))
                result = checker.check(samples, {})

                distributions.append(
                    {
                        "file": Path(file_path).name,
                        "count": len(samples),
                        "dist": result.distribution,
                    }
                )

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
                severity_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    rule.severity.value, "⚪"
                )
                status = "✓" if rule.enabled else "✗"
                lines.append(f"- {status} **{rule.name}** {severity_icon}")
                lines.append(f"  - ID: `{rule.id}`")
                lines.append(f"  - {rule.description}")
                lines.append("")

            lines.extend(
                [
                    "## 预设规则集",
                    "- `default`: 通用规则",
                    "- `sft`: SFT 数据规则",
                    "- `preference`: 偏好数据规则",
                ]
            )

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "infer_schema":
            checker = DataChecker()
            schema = checker.infer_schema_file(
                arguments["data_path"],
                arguments.get("output_path"),
            )

            fields = schema.get("fields", {})
            field_count = len(fields)
            required_count = sum(1 for f in fields.values() if f.get("required"))

            lines = [
                "## Schema 推断结果",
                "",
                f"- 样本数: {schema.get('sample_count', 0)}",
                f"- 字段数: {field_count}",
                f"- 必填字段: {required_count}",
                "",
                "### 字段详情",
                "",
                "| 字段 | 类型 | 必填 | 约束 |",
                "|------|------|------|------|",
            ]

            for fname, fdef in fields.items():
                ftype = fdef.get("type", "-")
                req = "是" if fdef.get("required") else "否"
                constraints = []
                if "min_length" in fdef:
                    constraints.append(f"长度 {fdef['min_length']}-{fdef['max_length']}")
                if "enum" in fdef:
                    constraints.append(f"枚举 {fdef['enum']}")
                if "min_value" in fdef:
                    constraints.append(f"值 {fdef['min_value']}-{fdef['max_value']}")
                lines.append(f"| {fname} | {ftype} | {req} | {', '.join(constraints) or '-'} |")

            if arguments.get("output_path"):
                lines.extend(["", f"Schema 已保存: {arguments['output_path']}"])

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "fix_data":
            fixer = DataFixer()
            result = fixer.fix_file(
                arguments["data_path"],
                arguments["output_path"],
                strip_pii=arguments.get("strip_pii", False),
            )

            lines = [
                "## 数据修复结果",
                "",
                f"- 输入样本: {result.total_input}",
                f"- 输出样本: {result.total_output}",
            ]
            if result.duplicates_removed:
                lines.append(f"- 去除重复: {result.duplicates_removed}")
            if result.trimmed_count:
                lines.append(f"- 修剪空白: {result.trimmed_count} 个字段")
            if result.empty_removed:
                lines.append(f"- 移除空样本: {result.empty_removed}")
            if result.pii_redacted_count:
                lines.append(f"- PII 脱敏: {result.pii_redacted_count} 个字段")
            lines.extend(["", f"输出文件: {arguments['output_path']}"])

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "batch_check_directory":
            ruleset_name = arguments.get("ruleset", "default")
            if ruleset_name == "sft":
                rules = get_sft_ruleset()
            elif ruleset_name == "preference":
                rules = get_preference_ruleset()
            else:
                rules = RuleSet()

            checker = DataChecker(rules)
            pat = arguments.get("pattern")
            patterns = [p.strip() for p in pat.split(",")] if pat else None

            batch_result = checker.check_directory(
                arguments["directory"],
                schema_path=arguments.get("schema_path"),
                patterns=patterns,
                sample_count=arguments.get("sample_count"),
            )

            lines = [
                "## 批量数据质量检查结果",
                "",
                f"- 目录: `{batch_result.directory}`",
                f"- 文件数: {batch_result.total_files}",
                f"- 总样本: {batch_result.total_samples}",
                f"- **总通过率: {batch_result.overall_pass_rate:.1%}**",
                "",
                "### 文件明细",
                "",
                "| 文件 | 样本数 | 通过率 | 错误 | 警告 |",
                "|------|--------|--------|------|------|",
            ]

            for fp, fr in batch_result.file_results.items():
                lines.append(
                    f"| {fp} | {fr.total_samples} | {fr.pass_rate:.1%} "
                    f"| {fr.error_count} | {fr.warning_count} |"
                )

            if batch_result.skipped_files:
                lines.extend(["", f"### 跳过文件 ({len(batch_result.skipped_files)})"])
                for s in batch_result.skipped_files:
                    lines.append(f"- {s}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "check_drift":
            checker = DataChecker()
            samples_a, _ = checker._load_data(Path(arguments["data_path_a"]))
            samples_b, _ = checker._load_data(Path(arguments["data_path_b"]))
            if not samples_a or not samples_b:
                return [TextContent(type="text", text="错误: 数据文件为空")]

            fields_a = set(samples_a[0].keys())
            fields_b = set(samples_b[0].keys())
            shared = sorted(fields_a & fields_b)
            requested = arguments.get("fields")
            if requested:
                shared = [f for f in requested if f in shared]
            if not shared:
                return [TextContent(type="text", text="错误: 两个文件没有共有字段")]

            def _classify(vals: list) -> str:
                nums = [v for v in vals if isinstance(v, (int, float))]
                if len(nums) > len(vals) * 0.5:
                    return "numeric"
                strs = [v for v in vals if isinstance(v, str)]
                if strs:
                    unique_ratio = len(set(strs)) / len(strs) if strs else 1
                    if unique_ratio < 0.3:
                        return "categorical"
                    return "text"
                return "text"

            lines = [
                "## 分布漂移检测结果", "",
                f"- 文件 A: `{Path(arguments['data_path_a']).name}` ({len(samples_a)} 条)",
                f"- 文件 B: `{Path(arguments['data_path_b']).name}` ({len(samples_b)} 条)",
                f"- 共有字段: {len(shared)}", "",
            ]
            for field in shared:
                vals_a = [s.get(field) for s in samples_a if field in s]
                vals_b = [s.get(field) for s in samples_b if field in s]
                ftype = _classify(vals_a + vals_b)
                lines.append(f"### 字段: `{field}` (类型: {ftype})")
                lines.append("")
                if ftype == "numeric":
                    for label, vals in [("A", vals_a), ("B", vals_b)]:
                        nums = [v for v in vals if isinstance(v, (int, float))]
                        if nums:
                            avg = sum(nums) / len(nums)
                            lines.append(f"- {label}: count={len(nums)}, mean={avg:.2f}, min={min(nums)}, max={max(nums)}")
                elif ftype == "categorical":
                    dist_a = Counter(str(v) for v in vals_a)
                    dist_b = Counter(str(v) for v in vals_b)
                    all_cats = sorted(set(list(dist_a.keys()) + list(dist_b.keys())))
                    lines.append("| 类别 | A | B |")
                    lines.append("|------|---|---|")
                    for cat in all_cats[:20]:
                        lines.append(f"| {cat} | {dist_a.get(cat, 0)} | {dist_b.get(cat, 0)} |")
                else:
                    for label, vals in [("A", vals_a), ("B", vals_b)]:
                        lengths = [len(str(v)) for v in vals if v]
                        if lengths:
                            avg_len = sum(lengths) / len(lengths)
                            lines.append(f"- {label}: count={len(lengths)}, avg_len={avg_len:.0f}")
                lines.append("")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "check_leakage":
            checker = DataChecker()
            train_samples, _ = checker._load_data(Path(arguments["train_path"]))
            test_samples, _ = checker._load_data(Path(arguments["test_path"]))
            if not train_samples or not test_samples:
                return [TextContent(type="text", text="错误: 数据文件为空")]

            threshold = arguments.get("threshold", 0.9)
            key_fields = arguments.get("key_fields")
            if not key_fields:
                sample = train_samples[0]
                key_fields = [k for k, v in sample.items() if isinstance(v, str) and len(v) > 10]
                if not key_fields:
                    key_fields = [k for k, v in sample.items() if isinstance(v, str)]
            if not key_fields:
                return [TextContent(type="text", text="错误: 未找到可比较的文本字段")]

            def _make_key(s: dict, fields: list) -> str:
                return "|||".join(str(s.get(f, "")).strip() for f in fields)

            train_keys: Dict[str, int] = {}
            for i, s in enumerate(train_samples):
                k = _make_key(s, key_fields)
                if k not in train_keys:
                    train_keys[k] = i

            exact_dupes = []
            for j, s in enumerate(test_samples):
                k = _make_key(s, key_fields)
                if k in train_keys:
                    exact_dupes.append((train_keys[k], j))

            # Near-duplicate via Jaccard
            def _tokenize(text: str) -> set:
                return set(text.lower().split())

            train_tokens = []
            for s in train_samples[:5000]:
                combined = " ".join(str(s.get(f, "")) for f in key_fields)
                train_tokens.append(_tokenize(combined))

            exact_test_idx = set(j for _, j in exact_dupes)
            near_dupes = []
            for j in range(min(len(test_samples), 500)):
                if j in exact_test_idx:
                    continue
                test_tok = _tokenize(" ".join(str(test_samples[j].get(f, "")) for f in key_fields))
                if not test_tok:
                    continue
                for i in range(len(train_tokens)):
                    inter = len(test_tok & train_tokens[i])
                    union = len(test_tok | train_tokens[i])
                    sim = inter / union if union else 0
                    if threshold <= sim < 1.0:
                        near_dupes.append((i, j, sim))
                        break

            total = len(test_samples)
            exact_rate = len(exact_dupes) / total * 100 if total else 0
            near_rate = len(near_dupes) / total * 100 if total else 0
            total_rate = (len(exact_dupes) + len(near_dupes)) / total * 100 if total else 0

            lines = [
                "## 数据泄漏检测结果", "",
                f"- 训练集: {len(train_samples)} 条",
                f"- 测试集: {len(test_samples)} 条",
                f"- 比较字段: {', '.join(key_fields)}",
                f"- 完全重复: {len(exact_dupes)} 条 ({exact_rate:.2f}%)",
                f"- 近似重复: {len(near_dupes)} 条 ({near_rate:.2f}%)",
                f"- **总泄漏: {len(exact_dupes) + len(near_dupes)} 条 ({total_rate:.2f}%)**",
            ]
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "check_bias":
            checker = DataChecker()
            samples, _ = checker._load_data(Path(arguments["data_path"]))
            if not samples:
                return [TextContent(type="text", text="错误: 数据文件为空")]

            label_field = arguments.get("label_field")
            text_field = arguments.get("text_field")
            dimensions = arguments.get("dimensions", ["all"])
            if "all" in dimensions:
                dimensions = ["category", "length", "language"]

            if not label_field or not text_field:
                sample = samples[0]
                for k, v in sample.items():
                    if not label_field and isinstance(v, str) and len(v) < 50:
                        unique_vals = set(s.get(k, "") for s in samples[:200])
                        if 2 <= len(unique_vals) <= 50:
                            label_field = k
                    if not text_field and isinstance(v, str) and len(v) >= 50:
                        text_field = k

            lines = [
                "## 数据偏差检测结果", "",
                f"- 文件: `{Path(arguments['data_path']).name}` ({len(samples)} 条)",
                f"- 标签字段: `{label_field or '(未指定)'}`",
                f"- 文本字段: `{text_field or '(未指定)'}`", "",
            ]

            if "category" in dimensions and label_field:
                labels = [s.get(label_field) for s in samples if label_field in s]
                counter = Counter(str(lb) for lb in labels if lb is not None)
                if counter:
                    sorted_cats = counter.most_common()
                    ratio = sorted_cats[0][1] / sorted_cats[-1][1] if sorted_cats[-1][1] > 0 else float("inf")
                    lines.append("### 类别分布")
                    lines.append(f"- 类别数: {len(counter)}, 不均衡比: {ratio:.1f}:1")
                    lines.append("| 类别 | 数量 | 占比 |")
                    lines.append("|------|------|------|")
                    total = sum(counter.values())
                    for cat, cnt in sorted_cats[:30]:
                        lines.append(f"| {cat} | {cnt} | {cnt / total * 100:.1f}% |")
                    lines.append("")

            if "length" in dimensions and text_field:
                lengths = [len(s.get(text_field, "")) for s in samples if isinstance(s.get(text_field), str)]
                if lengths:
                    avg = sum(lengths) / len(lengths)
                    variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
                    std = math.sqrt(variance)
                    lines.append("### 文本长度分布")
                    lines.append(f"- 平均: {avg:.0f}, 标准差: {std:.0f}, 范围: [{min(lengths)}, {max(lengths)}]")
                    lines.append("")

            if "language" in dimensions and text_field:
                lang_counter: Counter = Counter()
                for s in samples:
                    text = s.get(text_field, "")
                    if not isinstance(text, str) or not text:
                        continue
                    cjk = sum(1 for ch in text[:500] if "\u4e00" <= ch <= "\u9fff")
                    latin = sum(1 for ch in text[:500] if "\u0041" <= ch <= "\u007a")
                    total_c = cjk + latin or 1
                    if cjk / total_c > 0.3:
                        lang_counter["zh"] += 1
                    elif latin / total_c > 0.3:
                        lang_counter["en"] += 1
                    else:
                        lang_counter["other"] += 1
                if lang_counter:
                    lines.append("### 语言分布")
                    total_l = sum(lang_counter.values())
                    for lang, cnt in lang_counter.most_common():
                        lines.append(f"- {lang}: {cnt} ({cnt / total_l * 100:.1f}%)")
                    lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "check_coverage":
            checker = DataChecker()
            samples, _ = checker._load_data(Path(arguments["data_path"]))
            sample_count = arguments.get("sample_count")
            if sample_count and sample_count < len(samples):
                import random
                samples = random.sample(samples, sample_count)

            if not samples:
                return [TextContent(type="text", text="错误: 数据文件为空")]

            # Analyze field coverage
            all_fields: Dict[str, Dict[str, int]] = {}
            for s in samples:
                for field in s:
                    if field not in all_fields:
                        all_fields[field] = {"present": 0, "non_empty": 0, "unique_values": set()}
                    all_fields[field]["present"] += 1
                    val = s[field]
                    if val is not None and val != "" and val != []:
                        all_fields[field]["non_empty"] += 1
                        str_val = str(val)[:200]
                        if len(all_fields[field]["unique_values"]) < 10000:
                            all_fields[field]["unique_values"].add(str_val)

            total = len(samples)
            lines = [
                "## 数据覆盖度检测", "",
                f"- 文件: `{Path(arguments['data_path']).name}`",
                f"- 样本数: {total}",
                f"- 字段数: {len(all_fields)}", "",
                "| 字段 | 出现率 | 非空率 | 唯一值数 |",
                "|------|--------|--------|----------|",
            ]
            for field, stats in sorted(all_fields.items()):
                presence = stats["present"] / total * 100
                non_empty = stats["non_empty"] / total * 100
                unique = len(stats["unique_values"])
                lines.append(f"| {field} | {presence:.1f}% | {non_empty:.1f}% | {unique} |")

            # Overall coverage
            avg_presence = sum(s["present"] / total * 100 for s in all_fields.values()) / len(all_fields) if all_fields else 0
            avg_non_empty = sum(s["non_empty"] / total * 100 for s in all_fields.values()) / len(all_fields) if all_fields else 0
            lines.extend(["", f"**平均出现率: {avg_presence:.1f}%, 平均非空率: {avg_non_empty:.1f}%**"])

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
