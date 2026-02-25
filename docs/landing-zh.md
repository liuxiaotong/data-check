<div align="center">

<h1>DataCheck</h1>

<h3>多维数据质量验证框架<br/>Multi-Dimensional Data Quality Validation</h3>

<p><em>面向 LLM 训练数据的自动化质量验证——可组合规则、IQR/Z-score 异常检测、自动修复管线</em></p>

</div>

## 为什么选择 DataCheck？

训练数据质量是模型性能的隐性瓶颈。被忽略的格式错误、隐藏的 PII 泄露、未检测的重复样本——任何一个问题都可能在下游放大为系统性偏差。

现有质检方案要么是一次性脚本（不可复用），要么是重量级平台（部署成本高），且普遍缺少**统计异常检测**和**自动修复**能力。

**DataCheck** 通过**可组合规则引擎**提供端到端的数据质量验证：

- **9 条内置规则**，覆盖完整性、有效性、隐私、一致性四个质量维度
- **IQR / Z-score 双方法**异常检测，识别数值和文本长度异常值
- **LLM 辅助评估**，检查指令清晰度和回复相关性
- **自动修复管线** —— 去重、去空白、PII 脱敏
- **报告对比** —— 量化修复前后的质量改进

## 30 秒上手

```bash
pip install knowlyr-datacheck

# 检查你的数据
knowlyr-datacheck check data.json

# 自动修复问题
knowlyr-datacheck fix data.jsonl -o fixed.jsonl --strip-pii

# 对比修复前后
knowlyr-datacheck diff report_v1.json report_v2.json
```

## 质量管线 / Quality Pipeline

```mermaid
graph LR
    D["数据文件<br/>JSON / JSONL / CSV"] --> R["规则引擎<br/>9 条规则 + YAML 自定义"]
    R --> A["异常检测器<br/>IQR / Z-score"]
    A --> Rep["质量报告<br/>MD / JSON / HTML"]
    Rep --> Fix["自动修复<br/>去重 · PII · 去空白"]
    Fix --> Diff["报告对比<br/>修复前 vs 修复后"]

    style R fill:#0969da,color:#fff,stroke:#0969da
    style A fill:#8b5cf6,color:#fff,stroke:#8b5cf6
    style Rep fill:#2da44e,color:#fff,stroke:#2da44e
    style Fix fill:#e5534b,color:#fff,stroke:#e5534b
    style D fill:#1a1a2e,color:#e0e0e0,stroke:#444
    style Diff fill:#1a1a2e,color:#e0e0e0,stroke:#444
```

## 核心特性 / Core Features

### 可组合规则引擎 / Composable Rule Engine

9 条内置规则，4 种预设规则集（`default`、`sft`、`preference`、`llm`）。通过 YAML 扩展，无需写 Python 代码：

```yaml
rules:
  - field: instruction
    check: min_length
    value: 10
    severity: error
```

### 统计异常检测 / Statistical Anomaly Detection

纯 Python 实现，零外部依赖。样本量 $\geq 10$ 时自动启用：

- **IQR 方法**：$\text{outlier}(x) \iff x < Q_1 - 1.5 \cdot \text{IQR} \;\lor\; x > Q_3 + 1.5 \cdot \text{IQR}$
- **Z-score 方法**：$\text{outlier}(x) \iff |z(x)| > 3$

### LLM 辅助质量评估 / LLM-Assisted Quality Evaluation

超越规则检查的语义级质量评估：

```bash
knowlyr-datacheck check data.json --ruleset llm
```

### MCP 集成 / MCP Integration

11 个 MCP 工具，无缝集成 AI IDE——检查、修复、对比、推断 Schema，全部在编辑器中完成。

### Python SDK

```python
from datacheck import DataChecker, QualityReport

checker = DataChecker()
result = checker.check_file("data.json")
report = QualityReport(result)
report.print_summary()
```

## 生态系统 / Ecosystem

DataCheck 是 **knowlyr** 数据基础设施的一部分：

| 层 | 项目 | 职责 |
|:---|:---|:---|
| 发现 | **AI Dataset Radar** | 数据集竞争情报、趋势分析 |
| 分析 | **DataRecipe** | 逆向分析、Schema 提取、成本估算 |
| 生产 | **DataSynth** / **DataLabel** | LLM 批量合成 / 轻量标注 |
| 质量 | **DataCheck** | 规则验证、异常检测、自动修复 |
| 审计 | **ModelAudit** | 蒸馏检测、模型指纹 |

<div align="center">
<br/>
<a href="https://github.com/liuxiaotong/data-check">GitHub</a> · <a href="https://pypi.org/project/knowlyr-datacheck/">PyPI</a>
<br/><br/>
<sub><a href="https://github.com/liuxiaotong">knowlyr</a> — 多维数据质量验证框架，统计异常检测</sub>
</div>
