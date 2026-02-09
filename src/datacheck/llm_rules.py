"""LLM-based quality check rules."""

import json
from typing import Any, Dict, Optional


_QUALITY_PROMPT = """你是一个数据质量评审员。请评估以下 LLM 训练数据样本的质量。

## 样本数据
```json
{sample_json}
```

## 评估维度
1. **指令清晰度** (1-5): 指令是否明确、具体、无歧义
2. **回复相关性** (1-5): 回复是否直接回答了指令
3. **回复完整度** (1-5): 回复是否完整、充分
4. **整体质量** (1-5): 综合评分

## 输出格式
请严格以 JSON 格式输出，不要包含其他内容：
{{"instruction_clarity": <1-5>, "response_relevance": <1-5>, "response_completeness": <1-5>, "overall": <1-5>, "issues": ["问题1", "问题2"]}}"""


class LLMChecker:
    """LLM-based data quality checker.

    Requires: pip install knowlyr-datacheck[llm]
    """

    def __init__(self, provider: str = "anthropic", model: Optional[str] = None):
        self.provider = provider
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-init LLM client."""
        if self._client is not None:
            return self._client

        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("需要 anthropic 包。请运行: pip install knowlyr-datacheck[llm]")
            self._client = anthropic.Anthropic()
            self.model = self.model or "claude-sonnet-4-5-20250929"
        elif self.provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("需要 openai 包。请运行: pip install knowlyr-datacheck[llm]")
            self._client = openai.OpenAI()
            self.model = self.model or "gpt-4o-mini"
        else:
            raise ValueError(f"不支持的 provider: {self.provider}")

        return self._client

    def check_quality(self, sample: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check sample quality using LLM.

        Args:
            sample: Data sample
            schema: Data schema

        Returns:
            Dict with scores and issues
        """
        data = sample.get("data", sample)
        sample_json = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = _QUALITY_PROMPT.format(sample_json=sample_json)

        try:
            response_text = self._call_llm(prompt)
            result = json.loads(response_text)
            return result
        except (json.JSONDecodeError, Exception):
            return {"overall": 3, "issues": ["LLM 评估失败"]}

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM provider."""
        client = self._get_client()

        if self.provider == "anthropic":
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        elif self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        raise ValueError(f"不支持的 provider: {self.provider}")

    def make_check_fn(self, min_score: int = 3):
        """Create a rule check function.

        Args:
            min_score: Minimum overall score to pass (1-5)

        Returns:
            Check function compatible with Rule.check_fn
        """
        def check_fn(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
            result = self.check_quality(sample, schema)
            return result.get("overall", 3) >= min_score

        return check_fn
