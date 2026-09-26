from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = ""
    database_name: str = "ai_coding_mentor"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    judge0_url: str = Field(
        default="",
        validation_alias=AliasChoices("JUDGE0_API_URL", "JUDGE0_URL"),
    )
    judge0_api_key: str = ""
    judge0_poll_interval_seconds: float = 0.5
    judge0_max_poll_attempts: int = 20
    judge0_request_timeout_seconds: float = 10.0
    max_source_code_bytes: int = 50 * 1024
    max_stdin_bytes: int = 20 * 1024
    assessment_question_count: int = 5
    ml_monitoring_minimum_predictions: int = Field(default=30, ge=1)
    ml_monitoring_window_size: int = Field(default=500, ge=1)
    minimum_candidate_accuracy: float = Field(default=0.60, ge=0, le=1)
    minimum_candidate_f1: float = Field(default=0.60, ge=0, le=1)
    minimum_retraining_samples: int = Field(default=30, ge=12)
    minimum_new_training_rows: int = Field(default=30, ge=1)
    tutor_provider: str = "rule_based"
    tutor_max_code_length: int = Field(default=50000, ge=1, le=50000)
    tutor_max_hint_level: int = Field(default=4, ge=1, le=4)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
