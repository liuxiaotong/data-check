<div align="center">

<h1>DataCheck</h1>

<h3>Multi-Dimensional Data Quality Validation<br/>with Statistical Anomaly Detection</h3>

<p><em>Automated quality validation for LLM training data — composable rules, IQR/Z-score anomaly detection, and auto-fix pipeline</em></p>

</div>

## Why DataCheck?

Training data quality is the hidden bottleneck of model performance. Overlooked format errors, hidden PII leaks, undetected duplicate samples — any single issue can amplify into systematic bias downstream.

Existing quality solutions are either one-off scripts (not reusable) or heavyweight platforms (expensive to deploy), and generally lack **statistical anomaly detection** and **auto-fix** capabilities.

**DataCheck** solves this with a **composable rule engine** that provides end-to-end data quality validation:

- **9 Built-in Rules** covering completeness, validity, privacy, and consistency
- **IQR / Z-score Dual-Method** anomaly detection for numeric and text length outliers
- **LLM-Assisted Evaluation** for instruction clarity and response relevance
- **Auto-Fix Pipeline** — dedup, strip whitespace, PII redaction
- **Report Diff** — quantify quality improvements before vs. after fixes

## Get Started in 30 Seconds

```bash
pip install knowlyr-datacheck

# Check your data
knowlyr-datacheck check data.json

# Auto-fix issues
knowlyr-datacheck fix data.jsonl -o fixed.jsonl --strip-pii

# Compare before/after
knowlyr-datacheck diff report_v1.json report_v2.json
```

## Quality Pipeline

```mermaid
graph LR
    D["Data Files<br/>JSON / JSONL / CSV"] --> R["Rule Engine<br/>9 Rules + YAML Custom"]
    R --> A["Anomaly Detector<br/>IQR / Z-score"]
    A --> Rep["Quality Report<br/>MD / JSON / HTML"]
    Rep --> Fix["Auto Fix<br/>Dedup · PII · Trim"]
    Fix --> Diff["Report Diff<br/>Before vs After"]

    style R fill:#0969da,color:#fff,stroke:#0969da
    style A fill:#8b5cf6,color:#fff,stroke:#8b5cf6
    style Rep fill:#2da44e,color:#fff,stroke:#2da44e
    style Fix fill:#e5534b,color:#fff,stroke:#e5534b
    style D fill:#1a1a2e,color:#e0e0e0,stroke:#444
    style Diff fill:#1a1a2e,color:#e0e0e0,stroke:#444
```

## Core Features

### Composable Rule Engine

9 built-in rules with 4 preset rulesets (`default`, `sft`, `preference`, `llm`). Extend with YAML — no Python code needed:

```yaml
rules:
  - field: instruction
    check: min_length
    value: 10
    severity: error
```

### Statistical Anomaly Detection

Pure Python, zero external dependencies. Automatically enabled when sample size $\geq 10$:

- **IQR Method**: $\text{outlier}(x) \iff x < Q_1 - 1.5 \cdot \text{IQR} \;\lor\; x > Q_3 + 1.5 \cdot \text{IQR}$
- **Z-score Method**: $\text{outlier}(x) \iff |z(x)| > 3$

### LLM-Assisted Quality Evaluation

Semantic-level quality checks beyond rule-based validation:

```bash
knowlyr-datacheck check data.json --ruleset llm
```

### MCP Integration

11 MCP tools for seamless AI IDE integration — check, fix, diff, infer schema, and more, all from your editor.

### Python SDK

```python
from datacheck import DataChecker, QualityReport

checker = DataChecker()
result = checker.check_file("data.json")
report = QualityReport(result)
report.print_summary()
```

## Ecosystem

DataCheck is part of the **knowlyr** data infrastructure:

| Layer | Project | Role |
|:---|:---|:---|
| Discovery | **AI Dataset Radar** | Dataset intelligence & trend analysis |
| Analysis | **DataRecipe** | Reverse analysis, schema extraction, cost estimation |
| Production | **DataSynth** / **DataLabel** | LLM batch synthesis / lightweight annotation |
| Quality | **DataCheck** | Rule validation, anomaly detection, auto-fix |
| Audit | **ModelAudit** | Distillation detection, model fingerprinting |

<div align="center">
<br/>
<a href="https://github.com/liuxiaotong/data-check">GitHub</a> · <a href="https://pypi.org/project/knowlyr-datacheck/">PyPI</a>
<br/><br/>
<sub><a href="https://github.com/liuxiaotong">knowlyr</a> — multi-dimensional data quality validation with statistical anomaly detection</sub>
</div>
