from __future__ import annotations

from llm_control_center.auth import generate_api_key, hash_api_key, secure_compare
from llm_control_center.config import Settings


class TestSecureCompare:
    def test_equal_strings_return_true(self):
        assert secure_compare("abc", "abc") is True

    def test_different_strings_return_false(self):
        assert secure_compare("abc", "xyz") is False

    def test_empty_strings(self):
        assert secure_compare("", "") is True

    def test_different_lengths(self):
        assert secure_compare("abc", "abcd") is False


class TestGenerateApiKey:
    def test_default_prefix(self):
        key = generate_api_key()
        assert key.startswith("llmcc_")

    def test_custom_prefix(self):
        key = generate_api_key(prefix="custom")
        assert key.startswith("custom_")

    def test_unique_keys(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100


class TestHashApiKey:
    def test_deterministic(self):
        settings = Settings(api_key_pepper="test-pepper")
        key = "test_key_123"
        assert hash_api_key(key, settings) == hash_api_key(key, settings)

    def test_different_peppers_produce_different_hashes(self, monkeypatch):
        key = "test_key_123"
        monkeypatch.setenv("LLM_CC_API_KEY_PEPPER", "pepper1")
        settings1 = Settings()
        monkeypatch.setenv("LLM_CC_API_KEY_PEPPER", "pepper2")
        settings2 = Settings()
        assert hash_api_key(key, settings1) != hash_api_key(key, settings2)

    def test_different_keys_produce_different_hashes(self):
        settings = Settings(api_key_pepper="test-pepper")
        assert hash_api_key("key1", settings) != hash_api_key("key2", settings)
