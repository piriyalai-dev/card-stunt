"""Regression: `.env` ที่เว้น SUPER_ADMIN_ID ว่างต้องไม่ทำให้ Settings crash."""
import pytest

from core.config import Settings


def _settings(**overrides):
    base = dict(
        DATABASE_URL="postgresql://x:y@localhost:5432/z",
        API_KEY="k",
        SECRET_KEY="s",
        JWT_SECRET="j",
    )
    base.update(overrides)
    return Settings(**base)


def test_super_admin_blank_string_becomes_zero():
    assert _settings(SUPER_ADMIN_ID="").SUPER_ADMIN_ID == 0
    assert _settings(SUPER_ADMIN_ID="   ").SUPER_ADMIN_ID == 0


def test_super_admin_integer_still_works():
    assert _settings(SUPER_ADMIN_ID=123).SUPER_ADMIN_ID == 123
    assert _settings(SUPER_ADMIN_ID="456").SUPER_ADMIN_ID == 456


def test_cors_origins_default_includes_deployed_frontend():
    s = _settings()
    origins = [o.strip() for o in s.CORS_ORIGINS.split(",")]
    assert "https://pixel.singto1597.xyz" in origins


# ── Docker secrets (Wave 7) ────────────────────────────────────────

def test_secret_field_raises_when_empty_and_no_secret(monkeypatch):
    """ค่า sensitive ว่าง + ไม่มี /run/secrets/<name> → ต้อง fail ตอน boot (เหมือน field required เดิม)."""
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(ValueError, match="API_KEY ไม่ถูกตั้ง"):
        Settings(DATABASE_URL="postgresql://x:y@localhost:5432/z", API_KEY="", SECRET_KEY="s", JWT_SECRET="j")


def test_database_url_password_injected_from_env(monkeypatch):
    """URL ที่ไม่มี password (`user@host/db`) → ต่อ password จาก POSTGRES_PASSWORD."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
    s = Settings(
        DATABASE_URL="postgresql://pixelstand@pixelstand_infra_db:5432/pixelstand_db",
        API_KEY="k", SECRET_KEY="s", JWT_SECRET="j",
    )
    assert s.DATABASE_URL == "postgresql://pixelstand:s3cret@pixelstand_infra_db:5432/pixelstand_db"


def test_database_url_with_password_left_untouched(monkeypatch):
    """URL ที่มี password อยู่แล้ว → อย่าแตะ."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
    s = Settings(DATABASE_URL="postgresql://u:pass@localhost:5432/db", API_KEY="k", SECRET_KEY="s", JWT_SECRET="j")
    assert s.DATABASE_URL == "postgresql://u:pass@localhost:5432/db"
