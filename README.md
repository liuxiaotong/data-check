<div align="center">

# DataCheck

**数据质检工具 — 自动化质量检查、异常检测、分布分析**
**Automated quality checks, anomaly detection & distribution analysis for LLM datasets**

[![PyPI](https://img.shields.io/pypi/v/knowlyr-datacheck?color=blue)](https://pypi.org/project/knowlyr-datacheck/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-4_Tools-purple.svg)](#mcp-server)

[快速开始](#快速开始) · [质量规则](#质量规则) · [分布分析](#分布分析) · [MCP Server](#mcp-server) · [Data Pipeline 生态](#data-pipeline-生态)

</div>

---

**GitHub Topics**: `data-quality`, `anomaly-detection`, `data-validation`, `mcp`, `ai-data-pipeline`

自动化数据质量检查，支持规则验证、重复检测、分布分析，生成可读的质量报告。

## 核心能力 / Core Capabilities

```
数据文件 + Schema → 规则检查 → 异常检测 → 分布分析 → 质量报告
```

### 质量仪表盘预览 / Sample Dashboard

```
┌───────────────┬──────────────┬────────────┐
│ 通过率 92%    │ 评级 🟢 优秀 │ 错误 8 条 │
├───────────────┴──────────────┴────────────┤
│ ⚠ required_fields : 3  │ ⚠ duplicate_rows : 2│
│ 🔍 语言分布: zh 68% / en 32%                │
└────────────────────────────────────────────┘

完整示例: `examples/reports/demo_quality_report.md`
```

### 检查项目 / Checks

| 检查类型 | 说明 |
|----------|------|
| 🔴 **必填字段** | 检查是否包含所有必填字段 |
| 🔴 **非空检查** | 检查关键字段是否为空 |
| 🔴 **格式检查** | 检查数据类型是否正确 |
| 🟡 **长度边界** | 检查文本长度是否合理 |
| 🟡 **重复检测** | 检测重复样本 |
| 🔵 **语言一致性** | 检查文本语言是否一致 |

### 质量评级 / Rating

| 通过率 | 评级 | 建议 |
|--------|------|------|
| ≥90% | 🟢 优秀 | 可直接使用 |
| ≥70% | 🟡 良好 | 建议修复警告 |
| ≥50% | 🟠 一般 | 需要处理错误 |
| <50% | 🔴 需改进 | 严重质量问题 |

## 安装 / Installation

```bash
pip install knowlyr-datacheck
```

可选依赖：

```bash
pip install knowlyr-datacheck[stats]    # 统计分析 (numpy, scipy)
pip install knowlyr-datacheck[mcp]      # MCP 服务器
pip install knowlyr-datacheck[all]      # 全部功能
```

## 快速开始 / Quick Start

### 检查数据文件 / CLI

```bash
# 基础检查
knowlyr-datacheck check data.json

# 指定 Schema
knowlyr-datacheck check data.json -s schema.json

# 输出报告
knowlyr-datacheck check data.json -o report.md
```

### 在 Python 中接入 / Python SDK

```python
from datacheck import DataChecker, QualityReport

checker = DataChecker(schema_path="schema.json")
result = checker.check_file("data.json")

report = QualityReport.from_result(result)
print(report.summary())         # CLI 同款摘要
report.save("./report.md")
```

<details>
<summary>输出示例</summary>

```
正在检查 data.json...

==================================================
  数据质量检查结果
==================================================
  总样本: 100
  通过: 92
  失败: 8
  通过率: 92.0%
  评级: 🟢 优秀
==================================================

🟡 警告: 3
⚠️  重复: 2 组
```

</details>

### 使用 DataRecipe 分析结果验证 / Validate DataRecipe Outputs

```bash
# 验证合成数据
knowlyr-datacheck validate ./analysis_output/my_dataset/

# 验证指定文件
knowlyr-datacheck validate ./analysis_output/my_dataset/ -d custom_data.json
```

<details>
<summary>输出示例</summary>

```
正在验证 ./analysis_output/my_dataset/...
✓ 报告已保存: ./analysis_output/my_dataset/12_质检报告/quality_report.md

==================================================
  数据质量检查结果
==================================================
  总样本: 1000
  通过: 956
  失败: 44
  通过率: 95.6%
  评级: 🟢 优秀
==================================================
```

</details>

---

## 质量规则 / Quality Rules

### 内置规则 / Built-in Rules

```bash
# 查看所有规则
knowlyr-datacheck rules
```

| 规则 ID | 名称 | 级别 | 说明 |
|---------|------|------|------|
| `required_fields` | 必填字段检查 | 🔴 错误 | 检查必填字段是否存在 |
| `non_empty` | 非空检查 | 🔴 错误 | 检查关键字段是否为空 |
| `format_valid` | 格式检查 | 🔴 错误 | 检查数据类型是否正确 |
| `length_bounds` | 长度边界检查 | 🟡 警告 | 检查文本长度范围 |
| `score_valid` | 评分有效性 | 🔴 错误 | 检查评分是否在有效范围 |
| `language_consistency` | 语言一致性 | 🔵 提示 | 检查语言是否一致 |

### 预设规则集 / Rule Packs

```bash
# 使用 SFT 数据规则集
knowlyr-datacheck check data.json --ruleset sft

# 使用偏好数据规则集
knowlyr-datacheck check data.json --ruleset preference
```

| 规则集 | 说明 |
|--------|------|
| `default` | 通用规则 |
| `sft` | SFT 数据专用规则 (指令质量、回复质量) |
| `preference` | 偏好数据专用规则 (chosen/rejected 差异) |

### 自定义规则示例 / Custom Rule Example

```python
# my_rules.py
from datacheck.rules import register_rule, RuleResult

@register_rule(id="jsonl_line_length", level="warning")
def line_length(sample):
    if len(sample["instruction"]) > 2048:
        return RuleResult.fail(message="instruction 超出 2048 字符")
    return RuleResult.pass_()
```

```bash
knowlyr-datacheck check data.json --ruleset custom --extra-rules my_rules.py
```

> 规则打包：将多个规则放入 `rulesets/my_team.yaml` 并在 CLI 中通过 `--ruleset my_team` 调用，可与团队共享。

---

## 分布分析 / Distribution Analysis

### 对比多个数据文件

```bash
knowlyr-datacheck compare seed.json synthetic.json -o comparison.md
```

<details>
<summary>输出示例</summary>

```markdown
# 数据分布对比报告

## 文件概要

| 文件 | 样本数 |
|------|--------|
| seed.json | 50 |
| synthetic.json | 1000 |

## 字段对比

### instruction
- **seed.json**: 长度 15-200 (平均 68)
- **synthetic.json**: 长度 12-198 (平均 72)

### response
- **seed.json**: 长度 50-800 (平均 245)
- **synthetic.json**: 长度 45-820 (平均 251)
```

</details>

### 分析内容

- **长度统计**: 最小值、最大值、平均值
- **唯一值比例**: 检测多样性
- **值分布**: 数值型字段的分布情况
- **参考对比**: 与种子数据的分布差异

---

## MCP Server

在 Claude Desktop / Claude Code 中直接使用。

### 配置

添加到 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "knowlyr-datacheck": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-check", "run", "python", "-m", "datacheck.mcp_server"]
    }
  }
}
```

### 可用工具

| 工具 | 功能 |
|------|------|
| `check_data_quality` | 检查数据文件质量 |
| `validate_from_datarecipe` | 使用 DataRecipe 分析结果验证 |
| `compare_distributions` | 对比多个数据文件分布 |
| `list_quality_rules` | 列出所有质量检查规则 |

### 使用示例

```
用户: 帮我检查 ./output/synthetic.json 的质量

Claude: [调用 check_data_quality]

        ## 数据质量检查结果

        - 通过率: **95.6%**
        - 评级: **🟢 优秀**
        - 错误: 0, 警告: 44

        发现 2 组重复数据
```

---

## Data Pipeline 生态

DataCheck 是 Data Pipeline 生态的质检组件：

```mermaid
graph LR
    Radar["🔍 Radar<br/>情报发现"] --> Recipe["📋 Recipe<br/>逆向分析"]
    Recipe --> Synth["🔄 Synth<br/>数据合成"]
    Recipe --> Label["🏷️ Label<br/>数据标注"]
    Synth --> Check["✅ Check<br/>数据质检"]
    Label --> Check
    Check --> Audit["🔬 Audit<br/>模型审计"]
    Audit --> Hub["🎯 Hub<br/>编排层"]
    Hub --> Sandbox["📦 Sandbox<br/>执行沙箱"]
    Sandbox --> Recorder["📹 Recorder<br/>轨迹录制"]
    Recorder --> Reward["⭐ Reward<br/>过程打分"]
    style Check fill:#0969da,color:#fff,stroke:#0969da
```

### 生态项目

| 层 | 项目 | PyPI 包 | 说明 | 仓库 |
|---|---|---|---|---|
| 情报 | **AI Dataset Radar** | knowlyr-radar | 数据集竞争情报、趋势分析 | [GitHub](https://github.com/liuxiaotong/ai-dataset-radar) |
| 分析 | **DataRecipe** | knowlyr-datarecipe | 逆向分析、Schema 提取、成本估算 | [GitHub](https://github.com/liuxiaotong/data-recipe) |
| 生产 | **DataSynth** | knowlyr-datasynth | LLM 批量合成、种子数据扩充 | [GitHub](https://github.com/liuxiaotong/data-synth) |
| 生产 | **DataLabel** | knowlyr-datalabel | 轻量标注工具、多标注员合并 | [GitHub](https://github.com/liuxiaotong/data-label) |
| 质检 | **DataCheck** | knowlyr-datacheck | 规则验证、重复检测、分布分析 | You are here |
| 质检 | **ModelAudit** | knowlyr-modelaudit | 蒸馏检测、模型指纹、身份验证 | [GitHub](https://github.com/liuxiaotong/model-audit) |
| Agent | **knowlyr-agent** | knowlyr-sandbox / recorder / reward / hub | 沙箱 + 轨迹录制 + Reward + 编排 | [GitHub](https://github.com/liuxiaotong/knowlyr-agent) |

### 端到端工作流

```bash
# 1. DataRecipe: 分析数据集，生成 Schema 和样例
knowlyr-datarecipe deep-analyze tencent/CL-bench -o ./output

# 2. DataLabel: 生成标注界面，人工标注/校准种子数据
knowlyr-datalabel generate ./output/tencent_CL-bench/

# 3. DataSynth: 基于种子数据批量合成
knowlyr-datasynth generate ./output/tencent_CL-bench/ -n 1000

# 4. DataCheck: 质量检查
knowlyr-datacheck validate ./output/tencent_CL-bench/
```

### 四合一 MCP 配置

```json
{
  "mcpServers": {
    "knowlyr-datarecipe": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-recipe", "run", "knowlyr-datarecipe-mcp"]
    },
    "knowlyr-datalabel": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-label", "run", "python", "-m", "datalabel.mcp_server"]
    },
    "knowlyr-datasynth": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-synth", "run", "python", "-m", "datasynth.mcp_server"]
    },
    "knowlyr-datacheck": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-check", "run", "python", "-m", "datacheck.mcp_server"]
    }
  }
}
```

---

## 命令参考

| 命令 | 功能 |
|------|------|
| `knowlyr-datacheck check <file>` | 检查数据文件 |
| `knowlyr-datacheck check <file> -s <schema>` | 使用 Schema 检查 |
| `knowlyr-datacheck check <file> --ruleset sft` | 使用指定规则集 |
| `knowlyr-datacheck validate <dir>` | 验证 DataRecipe 输出 |
| `knowlyr-datacheck compare <files...>` | 对比多个文件分布 |
| `knowlyr-datacheck rules` | 列出所有规则 |

---

## API 使用

```python
from datacheck import DataChecker, QualityReport, RuleSet

# 创建检查器
checker = DataChecker()

# 检查数据
result = checker.check(samples, schema)

print(f"通过率: {result.pass_rate:.1%}")
print(f"错误: {result.error_count}")
print(f"重复: {len(result.duplicates)} 组")

# 生成报告
report = QualityReport(result)
report.save("report.md")
```

---

## 项目架构

```
src/datacheck/
├── checker.py        # 核心检查器
├── rules.py          # 规则定义和预设
├── report.py         # 报告生成
├── cli.py            # CLI 命令行
└── mcp_server.py     # MCP Server (4 工具)
```

---

## License

[MIT](LICENSE)

<div align="center">
<sub><a href="https://github.com/liuxiaotong">knowlyr</a> 数据工程生态 · 自动化数据质检</sub>
</div>
