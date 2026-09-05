"""
Configuration management using pydantic-settings.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Mode
    DRY_RUN: bool = True
    DEBUG: bool = False
    OUTBOX_DIR: str = "outbox"
    REQUEST_DELAY_SECONDS: float = 1.5

    # Email / SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_NAME: str = "Job Applicant"
    SENDER_EMAIL: str = ""

    # Candidate defaults
    DEFAULT_RESUME_PATH: str = "sample_data/sample_resume.txt"

    # AI Provider Settings (OpenAI / Gemini / Ollama compatible)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"

    # Contact Enrichment API Keys (Optional)
    HUNTER_API_KEY: Optional[str] = None
    APOLLO_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def resolve_outbox_path(self, base_dir: Optional[Path] = None) -> Path:
        base = base_dir or Path.cwd()
        path = base / self.OUTBOX_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
