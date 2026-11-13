"""Key resolution, encryption round-trip, and rate-limit window tests."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from src.config import settings
from src.db.models import AiUsage, UserLlmKey
from src.services import crypto
from src.services.llm import key_resolution


@pytest.fixture(autouse=True)
def clean_llm_settings(monkeypatch, tmp_path):
    """Reset LLM settings around each test in this module."""
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_allow_personal_keys", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_rate_limit_15min", 20)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_model", "")
    # Isolate data/encryption.key so a developer's local key file
    # cannot leak into encryption-state assertions.
    monkeypatch.setattr(settings, "data_dir", tmp_path)


def write_key_file(data_dir, key: str) -> None:
    """Create data/encryption.key with the given key content."""
    (data_dir / "encryption.key").write_text(key, encoding="utf-8")


class TestCrypto:
    def test_round_trip(self):
        enc = crypto.encrypt_key("sk-secret-123")
        assert enc != "sk-secret-123"
        assert crypto.decrypt_key(enc) == "sk-secret-123"

    def test_mask(self):
        assert crypto.mask_key("sk-abcdefghijklmnop") == "sk-...mnop"

    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "")
        assert not crypto.encryption_available()
        assert crypto.decrypt_key("x") is None
        with pytest.raises(ValueError):
            crypto.encrypt_key("x")

    def test_file_fallback_when_env_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "encryption_key", "")
        write_key_file(tmp_path, Fernet.generate_key().decode())
        assert crypto.encryption_issue() is None
        assert crypto.encryption_available()
        enc = crypto.encrypt_key("sk-secret-123")
        assert crypto.decrypt_key(enc) == "sk-secret-123"

    def test_not_configured_without_env_or_file(self, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "")
        assert crypto.encryption_issue() == "server encryption key not configured"

    def test_invalid_env_does_not_fall_back_to_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "encryption_key", "not-a-fernet-key")
        write_key_file(tmp_path, Fernet.generate_key().decode())
        assert crypto.encryption_issue() == (
            "server encryption key is set but invalid (expected a Fernet key)"
        )
        # The valid file key must NOT be used while env is set.
        with pytest.raises(ValueError):
            crypto.encrypt_key("x")

    def test_invalid_env_without_file(self, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "not-a-fernet-key")
        assert crypto.encryption_issue() == (
            "server encryption key is set but invalid (expected a Fernet key)"
        )

    def test_bad_ciphertext(self):
        assert crypto.decrypt_key("not-a-fernet-token") is None


class TestKeyResolution:
    def test_personal_wins_over_enterprise(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="m1",
            api_key_encrypted=crypto.encrypt_key("sk-personal"),
        ))
        db.commit()
        r = key_resolution.resolve(db, u.id)
        assert r.mode == "personal"
        assert r.api_key == "sk-personal"

    def test_enterprise_fallback(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_model", "gpt-x")
        r = key_resolution.resolve(db, u.id)
        assert r.mode == "enterprise"
        assert r.api_key == "sk-enterprise"
        assert r.model == "gpt-x"

    def test_none_raises_403(self, db, user):
        u, _ = user
        with pytest.raises(Exception) as exc:
            key_resolution.resolve(db, u.id)
        assert getattr(exc.value, "status_code", None) == 403

    def test_personal_disallowed(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_allow_personal_keys", False)
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="m1",
            api_key_encrypted=crypto.encrypt_key("sk-personal"),
        ))
        db.commit()
        # No enterprise key -> 403 with the admin message
        with pytest.raises(Exception) as exc:
            key_resolution.resolve(db, u.id)
        assert getattr(exc.value, "status_code", None) == 403

    def test_disabled_kill_switch(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_enabled", False)
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        with pytest.raises(Exception) as exc:
            key_resolution.resolve(db, u.id)
        assert getattr(exc.value, "status_code", None) == 403

    def test_personal_unavailable_without_encryption(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "encryption_key", "")
        with pytest.raises(Exception) as exc:
            key_resolution.resolve(db, u.id)
        assert getattr(exc.value, "status_code", None) == 403
        assert "encryption" in exc.value.detail.lower()

    def test_personal_works_with_file_key_fallback(self, db, user, monkeypatch, tmp_path):
        u, _ = user
        monkeypatch.setattr(settings, "encryption_key", "")
        write_key_file(tmp_path, Fernet.generate_key().decode())
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="m1",
            api_key_encrypted=crypto.encrypt_key("sk-personal"),
        ))
        db.commit()
        r = key_resolution.resolve(db, u.id)
        assert r.mode == "personal"
        assert r.api_key == "sk-personal"


class TestRateLimit:
    def test_window_counting_and_429(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_rate_limit_15min", 2)
        # Two recent calls -> limit reached
        for _ in range(2):
            db.add(AiUsage(user_id=u.id, ts=datetime.now(UTC), tokens=10))
        db.commit()
        with pytest.raises(Exception) as exc:
            key_resolution.resolve(db, u.id)
        assert getattr(exc.value, "status_code", None) == 429
        assert exc.value.headers.get("Retry-After")

    def test_old_rows_do_not_count(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_rate_limit_15min", 2)
        old = datetime.now(UTC) - timedelta(minutes=16)
        db.add(AiUsage(user_id=u.id, ts=old, tokens=10))
        db.commit()
        r = key_resolution.resolve(db, u.id)
        assert r.mode == "enterprise"
        assert r.remaining == 2  # old row not counted, 0 recent of limit 2

    def test_zero_limit_is_unlimited(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_rate_limit_15min", 0)
        for _ in range(50):
            db.add(AiUsage(user_id=u.id, ts=datetime.now(UTC), tokens=1))
        db.commit()
        r = key_resolution.resolve(db, u.id)
        assert r.rate_limit is None

    def test_personal_never_limited(self, db, user, monkeypatch):
        u, _ = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_rate_limit_15min", 1)
        db.add(AiUsage(user_id=u.id, ts=datetime.now(UTC), tokens=1))
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="m1",
            api_key_encrypted=crypto.encrypt_key("sk-personal"),
        ))
        db.commit()
        r = key_resolution.resolve(db, u.id)
        assert r.mode == "personal"
        assert r.rate_limit is None


class TestFernetKeyFormat:
    def test_generated_key_is_valid_fernet(self):
        key = Fernet.generate_key()
        Fernet(key)  # must not raise
