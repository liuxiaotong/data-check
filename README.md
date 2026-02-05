<div align="center">

# DataCheck

**数据质检工具 - 自动化质量检查、异常检测、分布分析**

[![PyPI](https://img.shields.io/pypi/v/datacheck?color=blue)](https://pypi.org/project/datacheck/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-4_Tools-purple.svg)](#mcp-server)

[快速开始](#快速开始) · [质量规则](#质量规则) · [分布分析](#分布分析) · [MCP Server](#mcp-server) · [Data Pipeline 生态](#data-pipeline-生态)

</div>

---

自动化数据质量检查，支持规则验证、重复检测、分布分析，生成可读的质量报告。

## 核心能力

```
数据文件 + Schema → 规则检查 → 异常检测 → 分布分析 → 质量报告
```

### 检查项目

| 检查类型 | 说明 |
|----------|------|
| 🔴 **必填字段** | 检查是否包含所有必填字段 |
| 🔴 **非空检查** | 检查关键字段是否为空 |
| 🔴 **格式检查** | 检查数据类型是否正确 |
| 🟡 **长度边界** | 检查文本长度是否合理 |
| 🟡 **重复检测** | 检测重复样本 |
| 🔵 **语言一致性** | 检查文本语言是否一致 |

### 质量评级

| 通过率 | 评级 | 建议 |
|--------|------|------|
| ≥90% | 🟢 优秀 | 可直接使用 |
| ≥70% | 🟡 良好 | 建议修复警告 |
| ≥50% | 🟠 一般 | 需要处理错误 |
| <50% | 🔴 需改进 | 严重质量问题 |

## 安装

```bash
pip install datacheck
```

可选依赖：

```bash
pip install datacheck[stats]    # 统计分析 (numpy, scipy)
pip install datacheck[mcp]      # MCP 服务器
pip install datacheck[all]      # 全部功能
```

## 快速开始

### 检查数据文件

```bash
# 基础检查
datacheck check data.json

# 指定 Schema
datacheck check data.json -s schema.json

# 输出报告
datacheck check data.json -o report.md
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

### 使用 DataRecipe 分析结果验证

```bash
# 验证合成数据
datacheck validate ./analysis_output/my_dataset/

# 验证指定文件
datacheck validate ./analysis_output/my_dataset/ -d custom_data.json
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

## 质量规则

### 内置规则

```bash
# 查看所有规则
datacheck rules
```

| 规则 ID | 名称 | 级别 | 说明 |
|---------|------|------|------|
| `required_fields` | 必填字段检查 | 🔴 错误 | 检查必填字段是否存在 |
| `non_empty` | 非空检查 | 🔴 错误 | 检查关键字段是否为空 |
| `format_valid` | 格式检查 | 🔴 错误 | 检查数据类型是否正确 |
| `length_bounds` | 长度边界检查 | 🟡 警告 | 检查文本长度范围 |
| `score_valid` | 评分有效性 | 🔴 错误 | 检查评分是否在有效范围 |
| `language_consistency` | 语言一致性 | 🔵 提示 | 检查语言是否一致 |

### 预设规则集

```bash
# 使用 SFT 数据规则集
datacheck check data.json --ruleset sft

# 使用偏好数据规则集
datacheck check data.json --ruleset preference
```

| 规则集 | 说明 |
|--------|------|
| `default` | 通用规则 |
| `sft` | SFT 数据专用规则 (指令质量、回复质量) |
| `preference` | 偏好数据专用规则 (chosen/rejected 差异) |

---

## 分布分析

### 对比多个数据文件

```bash
datacheck compare seed.json synthetic.json -o comparison.md
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
    "datacheck": {
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

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Data Pipeline 生态                                │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│   DataRecipe     │    DataLabel     │    DataSynth     │     DataCheck      │
│     数据分析      │      数据标注     │      数据合成     │       数据质检      │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│  · 逆向工程分析   │  · HTML标注界面   │  · LLM批量生成    │  · 规则验证        │
│  · Schema提取    │  · 多标注员合并    │  · 种子数据扩充   │  · 重复检测        │
│  · 成本估算      │  · IAA一致性计算  │  · 成本追踪       │  · 分布分析        │
│  · 样例生成      │  · 断点续标       │  · 交互/API模式   │  · 质量报告        │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

### 生态项目

| 项目 | 功能 | 仓库 |
|------|------|------|
| **DataRecipe** | 数据集逆向分析 | [data-recipe](https://github.com/liuxiaotong/data-recipe) |
| **DataLabel** | 轻量级标注工具 | [data-label](https://github.com/liuxiaotong/data-label) |
| **DataSynth** | 数据合成扩充 | [data-synth](https://github.com/liuxiaotong/data-synth) |
| **DataCheck** | 数据质量检查 | [data-check](https://github.com/liuxiaotong/data-check) |

### 端到端工作流

```bash
# 1. DataRecipe: 分析数据集，生成 Schema 和样例
datarecipe deep-analyze tencent/CL-bench -o ./output

# 2. DataLabel: 生成标注界面，人工标注/校准种子数据
datalabel generate ./output/tencent_CL-bench/

# 3. DataSynth: 基于种子数据批量合成
datasynth generate ./output/tencent_CL-bench/ -n 1000

# 4. DataCheck: 质量检查
datacheck validate ./output/tencent_CL-bench/
```

### 四合一 MCP 配置

```json
{
  "mcpServers": {
    "datarecipe": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-recipe", "run", "datarecipe-mcp"]
    },
    "datalabel": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-label", "run", "python", "-m", "datalabel.mcp_server"]
    },
    "datasynth": {
      "command": "uv",
      "args": ["--directory", "/path/to/data-synth", "run", "python", "-m", "datasynth.mcp_server"]
    },
    "datacheck": {
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
| `datacheck check <file>` | 检查数据文件 |
| `datacheck check <file> -s <schema>` | 使用 Schema 检查 |
| `datacheck check <file> --ruleset sft` | 使用指定规则集 |
| `datacheck validate <dir>` | 验证 DataRecipe 输出 |
| `datacheck compare <files...>` | 对比多个文件分布 |
| `datacheck rules` | 列出所有规则 |

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

---

<div align="center">
<sub>为数据团队提供自动化质量保障</sub>
</div>
