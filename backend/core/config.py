from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pixel Stand API (ระบบแปรอักษรกีฬาสี)"
    PROJECT_VERSION: str = "0.2.0"
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

    # Media — reference image + thumbnail (signed URL/media เต็มมา Phase 5)
    MEDIA_STORAGE_DIR: str = "/data/media"
    MEDIA_MAX_UPLOAD_MB: int = 10
    MEDIA_MAX_DIMENSION: int = 10000
    MEDIA_THUMB_DIMENSION: int = 480

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
