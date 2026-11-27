"""Regression: `.env` ที่เว้น SUPER_ADMIN_ID ว่างต้องไม่ทำให้ Settings crash."""
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
