from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
