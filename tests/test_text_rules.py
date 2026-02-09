"""Tests for text quality detection rules."""

import pytest

from datacheck.checker import DataChecker
from datacheck.text_rules import (
    check_garbled_text,
    check_pii,
    check_repetitive_text,
    compute_ngrams,
    jaccard_similarity,
)


class TestPIIDetection:
    """Tests for PII detection rule."""

    def test_email_detected(self):
        sample = {"data": {"text": "Contact me at user@example.com for info"}}
        assert check_pii(sample, {}) is False

    def test_chinese_phone(self):
        sample = {"data": {"text": "我的电话是 13812345678"}}
        assert check_pii(sample, {}) is False

    def test_chinese_id(self):
        sample = {"data": {"text": "身份证号 11010119900101001X"}}
        assert check_pii(sample, {}) is False

    def test_international_phone(self):
        sample = {"data": {"text": "Call +86 13812345678"}}
        assert check_pii(sample, {}) is False

    def test_clean_text(self):
        sample = {"data": {"text": "This is a clean text with no PII information"}}
        assert check_pii(sample, {}) is True

    def test_non_string_values(self):
        sample = {"data": {"count": 42, "flag": True}}
        assert check_pii(sample, {}) is True

    def test_flat_sample(self):
        sample = {"text": "email: test@example.org"}
        assert check_pii(sample, {}) is False


class TestGarbledText:
    """Tests for garbled text detection rule."""

    def test_replacement_chars(self):
        sample = {"data": {"text": "Hello\ufffd\ufffd\ufffd" * 10}}
        assert check_garbled_text(sample, {}) is False

    def test_control_chars(self):
        sample = {"data": {"text": "text\x00\x01\x02" * 20}}
        assert check_garbled_text(sample, {}) is False

    def test_encoding_error(self):
        # Simulate mojibake: consecutive Latin-supplement chars (U+00C0..U+00FF)
        sample = {"data": {"text": "This is \u00c3\u00c9\u00d1\u00e8\u00fc\u00c0 mojibake"}}
        assert check_garbled_text(sample, {}) is False

    def test_clean_text(self):
        sample = {"data": {"text": "This is normal text with Chinese 中文内容"}}
        assert check_garbled_text(sample, {}) is True

    def test_short_text_ignored(self):
        sample = {"data": {"text": "Hi"}}
        assert check_garbled_text(sample, {}) is True


class TestRepetitiveText:
    """Tests for repetitive text detection rule."""

    def test_sentence_repetition(self):
        sample = {"data": {"text": "This is repeated. " * 50}}
        assert check_repetitive_text(sample, {}) is False

    def test_character_repetition(self):
        sample = {"data": {"text": "哈哈哈哈哈哈哈哈哈哈" * 20}}
        assert check_repetitive_text(sample, {}) is False

    def test_normal_text(self):
        sample = {
            "data": {
                "text": "First sentence here. Second sentence here. Third one is different. Fourth is unique too."
            }
        }
        assert check_repetitive_text(sample, {}) is True

    def test_short_text_ignored(self):
        sample = {"data": {"text": "Short."}}
        assert check_repetitive_text(sample, {}) is True


class TestNgramHelpers:
    """Tests for n-gram helper functions."""

    def test_compute_ngrams(self):
        ngrams = compute_ngrams("hello", n=3)
        assert "hel" in ngrams
        assert "ell" in ngrams
        assert "llo" in ngrams
        assert len(ngrams) == 3

    def test_compute_ngrams_short(self):
        ngrams = compute_ngrams("hi", n=3)
        assert ngrams == {"hi"}

    def test_compute_ngrams_empty(self):
        ngrams = compute_ngrams("", n=3)
        assert ngrams == set()

    def test_jaccard_identical(self):
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_jaccard_disjoint(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_jaccard_partial(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert sim == pytest.approx(0.5)

    def test_jaccard_empty(self):
        assert jaccard_similarity(set(), set()) == 1.0


class TestNearDuplicateDetection:
    """Tests for near-duplicate detection in DataChecker."""

    def test_near_duplicates_found(self):
        samples = [
            {"id": "1", "data": {"text": "The quick brown fox jumps over the lazy dog"}},
            {"id": "2", "data": {"text": "The quick brown fox jumps over the lazy cat"}},
            {
                "id": "3",
                "data": {
                    "text": "Something completely different and unrelated to any fox or dog story"
                },
            },
        ]
        checker = DataChecker()
        result = checker.check(samples, {})
        assert len(result.near_duplicates) >= 1

    def test_no_near_duplicates(self):
        samples = [
            {"id": "1", "data": {"text": "Artificial intelligence and machine learning are transformative"}},
            {"id": "2", "data": {"text": "Python is a programming language used widely for web development"}},
            {"id": "3", "data": {"text": "太阳系有八大行星围绕太阳运行"}},
        ]
        checker = DataChecker()
        result = checker.check(samples, {})
        assert len(result.near_duplicates) == 0
