"""Tests for LLM-based quality rules."""

import json
from unittest.mock import MagicMock

import pytest

from datacheck.llm_rules import LLMChecker


class TestLLMChecker:
    """Tests for LLMChecker with mocked LLM calls."""

    def test_check_quality_pass(self):
        checker = LLMChecker(provider="anthropic")
        checker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "instruction_clarity": 5,
            "response_relevance": 4,
            "response_completeness": 4,
            "overall": 4,
            "issues": [],
        }))]
        checker._client.messages.create.return_value = mock_response

        result = checker.check_quality(
            {"data": {"instruction": "What is AI?", "response": "AI is..."}}, {}
        )
        assert result["overall"] == 4
        assert result["issues"] == []

    def test_check_quality_fail(self):
        checker = LLMChecker(provider="anthropic")
        checker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "instruction_clarity": 2,
            "response_relevance": 1,
            "response_completeness": 1,
            "overall": 1,
            "issues": ["回复太短", "与指令无关"],
        }))]
        checker._client.messages.create.return_value = mock_response

        result = checker.check_quality(
            {"data": {"instruction": "Explain quantum physics", "response": "OK"}}, {}
        )
        assert result["overall"] == 1
        assert len(result["issues"]) == 2

    def test_check_quality_json_error(self):
        checker = LLMChecker(provider="anthropic")
        checker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        checker._client.messages.create.return_value = mock_response

        result = checker.check_quality({"data": {"text": "hello"}}, {})
        assert result["overall"] == 3  # fallback score

    def test_make_check_fn_pass(self):
        checker = LLMChecker(provider="anthropic")
        checker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({"overall": 4, "issues": []}))]
        checker._client.messages.create.return_value = mock_response

        check_fn = checker.make_check_fn(min_score=3)
        assert check_fn({"data": {"text": "hello"}}, {}) is True

    def test_make_check_fn_fail(self):
        checker = LLMChecker(provider="anthropic")
        checker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({"overall": 2, "issues": ["差"]}))]
        checker._client.messages.create.return_value = mock_response

        check_fn = checker.make_check_fn(min_score=3)
        assert check_fn({"data": {"text": "hello"}}, {}) is False

    def test_openai_provider(self):
        checker = LLMChecker(provider="openai")
        checker._client = MagicMock()

        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"overall": 5, "issues": []})
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        checker._client.chat.completions.create.return_value = mock_response

        # Need to set model since _get_client wasn't called
        checker.model = "gpt-4o-mini"

        result = checker.check_quality({"data": {"text": "hello"}}, {})
        assert result["overall"] == 5

    def test_unsupported_provider(self):
        with pytest.raises(ValueError, match="不支持的 provider"):
            checker = LLMChecker(provider="unknown")
            checker._get_client()
