import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(name: str) -> str | None:
    """อ่าน Docker secret (mount ที่ /run/secrets/<name>) — คืน None ถ้าไม่มี/ว่าง.

    ใช้กับค่า sensitive (API_KEY / SECRET_KEY / JWT_SECRET / DB password) ที่ควรอยู่เป็น
    swarm secret แทน env ⇒ ไม่โผล่ใน `docker service inspect` · บน host/ทดสอบไม่มีไฟล์นี้
    ⇒ fallback ไป env ตามเดิม (backward compatible)
    """
    path = f"/run/secrets/{name}"
    try:
        with open(path, encoding="utf-8") as f:
            value = f.read().strip()
        return value or None
    except OSError:
        return None


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pixel Stand API (ระบบแปรอักษรกีฬาสี)"
    PROJECT_VERSION: str = "0.4.0"
    # commit ที่ build image นี้ — ส่งมาจาก build arg (pull_all.sh / setup.sh)
    GIT_SHA: str = "unknown"

    DATABASE_URL: str
    # secrets — ค่าเริ่มต้น "" แล้ว validator อ่าน /run/secrets/<name> ถ้า env ว่าง (ดู _secret_or_required)
    API_KEY: str = ""
    SECRET_KEY: str = ""
    SUPER_ADMIN_ID: int = 0

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    # access token สั้น (ใช้ยิง API) · refresh token ยาว (เก็บใน httpOnly cookie) — ดู docs/4-developer-playbook
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # refresh cookie (httpOnly) — ชื่อ + ความปลอดภัย (เปิด Secure เมื่อมี HTTPS)
    REFRESH_COOKIE_NAME: str = "pixelstand_refresh"
    REFRESH_COOKIE_SECURE: bool = False

    # Rate limit login (กัน brute-force) — per IP + per username, fixed window
    LOGIN_RATE_LIMIT_MAX: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Rate limit การทำงาน bulk (upload reference image / import roster / สร้าง export) — per user
    BULK_OP_RATE_LIMIT_MAX: int = 60
    BULK_OP_RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # ขนาด request body สูงสุด (gateway กัน buffer ของใหญ่ก่อนถึง endpoint)
    MAX_REQUEST_BODY_MB: int = 20

    # CORS — origin ของ frontend ที่อนุญาตให้เรียก API (คั่นด้วย comma)
    # ค่าเริ่มต้นรวม dev server + โดเมนจริงของเครื่องนี้ (override ได้ผ่าน .env)
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://pixel.singto1597.xyz,http://pixel.singto1597.xyz"
    )

    # Seed users — ไฟล์เก็บ username + รหัสชั่วคราว (บังคับเปลี่ยนตอน login ครั้งแรก)
    SEED_CREDENTIALS_FILE: str = "default_admin_credentials.txt"

    # Redis — public cache + ETag (ว่าง = ปิด cache แล้วอ่านจาก DB ตรง ๆ)
    REDIS_URL: str = ""

    # Live sync (SSE) — PG LISTEN/NOTIFY channel ต้องตรงกับ trigger ใน migration 004
    # ⚠️ เปลี่ยนชื่อที่นี่ = เงียบทั้งระบบโดยไม่มี error (LISTEN ค้างบน channel ที่ไม่มีใครส่ง)
    NOTIFY_CHANNEL: str = "pixelstand_live"
    STREAM_HEARTBEAT_SECONDS: float = 20.0
    STREAM_MAX_SUBSCRIBERS: int = 2000

    # Public cache TTL (วินาที) — ETag ใช้ประกอบกับ `events.version`
    CACHE_META_TTL_SECONDS: int = 300
    CACHE_SEAT_TTL_SECONDS: int = 60

    # Media — reference image + thumbnail
    # served ผ่าน signed URL (HMAC) เพื่อให้ `<img src>` ใช้ได้โดยไม่ต้องแนบ Bearer token
    MEDIA_STORAGE_DIR: str = "/data/media"
    MEDIA_MAX_UPLOAD_MB: int = 10
    MEDIA_MAX_DIMENSION: int = 10000
    MEDIA_THUMB_DIMENSION: int = 480
    MEDIA_SIGNED_TTL_SECONDS: int = 900

    # Export — ไฟล์ PDF/CSV/ZIP ที่ ARQ worker สร้าง (relative path เก็บใน export_jobs.file_path)
    EXPORT_STORAGE_DIR: str = "/data/exports"
    EXPORT_MAX_AGE_DAYS: int = 7
    EXPORT_MAX_SEATS_PDF: int = 5000

    # Stunt revisions — เก็บ full snapshot ต่อครั้ง กันไม่ให้โตเกิน (design §11)
    REVISION_RETENTION: int = 20

    # Stand / grid limits (design §11: MAX_TOTAL_CELLS)
    MAX_TOTAL_CELLS: int = 200000

    # Roster import limits
    ROSTER_MAX_ROWS: int = 5000
    ROSTER_FILE_SIZE_LIMIT_MB: int = 5

    @field_validator("SUPER_ADMIN_ID", mode="before")
    @classmethod
    def _blank_super_admin_is_zero(cls, value):
        """`.env` ที่ตั้ง `SUPER_ADMIN_ID=` (เว้นว่าง) ต้องไม่ทำให้ container crash.

        ⚠️ pydantic-settings ใช้ค่าว่างจาก env ทับ default แล้วพยายามแปลงเป็น int
        ⇒ `ValidationError` ตอน import settings (เกิดจริงตอน deploy แรก)
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return 0
        return value

    @field_validator("API_KEY", "SECRET_KEY", "JWT_SECRET", mode="after")
    @classmethod
    def _secret_or_required(cls, value, info):
        """ค่า sensitive — อ่านจาก swarm secret ก่อน ถ้า env ว่าง แล้วค่อยบังคับ.

        Docker secret mount ที่ `/run/secrets/pixelstand_<field_name.lower()>` (เช่น
        `API_KEY` → `/run/secrets/pixelstand_api_key`) · ถ้าไม่มีทั้ง env และ secret → error
        ตอน boot (เหมือน field required เดิม)
        """
        if value:
            return value
        secret = _read_secret(f"pixelstand_{info.field_name.lower()}")
        if secret:
            return secret
        raise ValueError(f"{info.field_name} ไม่ถูกตั้ง — ใส่ใน .env หรือ Docker secret")

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _inject_db_password(cls, value):
        """DATABASE_URL ที่ไม่มี password (`user@host/db`) → ต่อ password จาก secret/env.

        compose ตั้ง URL โดยไม่ฝัง password ⇒ backend ประกอบ password เองจาก
        `pixelstand_postgres_password` (secret) หรือ `POSTGRES_PASSWORD` (env)
        """
        if not value:
            return value
        password = _read_secret("pixelstand_postgres_password") or os.environ.get("POSTGRES_PASSWORD", "")
        if password and "://" in value:
            scheme, rest = value.split("://", 1)
            userinfo, sep, hostport = rest.partition("@")
            if sep and ":" not in userinfo:
                return f"{scheme}://{userinfo}:{password}@{hostport}"
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
