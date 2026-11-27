from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pixel Stand API (ระบบแปรอักษรกีฬาสี)"
    PROJECT_VERSION: str = "0.1.0"
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
