from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pixel Stand API (ระบบแปรอักษรกีฬาสี)"
    PROJECT_VERSION: str = "0.4.0"
    # commit ที่ build image นี้ — ส่งมาจาก build arg (pull_all.sh / setup.sh)
    GIT_SHA: str = "unknown"

    DATABASE_URL: str
    API_KEY: str
    SECRET_KEY: str
    SUPER_ADMIN_ID: int = 0

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Rate limit login (กัน brute-force) — per IP + per username, fixed window
    LOGIN_RATE_LIMIT_MAX: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

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
    MAX_STAND_ROWS: int = 1000
    MAX_STAND_COLS: int = 1000
    MAX_SUB_SIZE: int = 16
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
