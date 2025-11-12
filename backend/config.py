"""
Configuration for GhostEye v2.
"""

import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = Field(default="development")
    
    # Supabase
    supabase_url: str = Field(default="http://localhost:54321", description="Supabase URL")
    supabase_key: str = Field(default="your_key_here", description="Supabase anon key")
    supabase_service_key: str = Field(default="your_service_key_here", description="Supabase service key")
    
    # Database
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:54322/postgres", description="PostgreSQL connection URL")
    use_in_memory_mode: bool = Field(default=False, description="Use in-memory mode (no database)")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Twilio
    twilio_account_sid: str = Field(default="your_sid", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="your_token", description="Twilio Auth Token")
    twilio_phone_number: str = Field(default="+1234567890", description="Twilio phone number")
    
    # LLM (OpenAI Direct)
    openai_api_key: str = Field(default="your_openai_key", description="OpenAI API key")
    llm_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    
    # Application
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for signing")
    api_version: str = Field(default="v2")
    log_level: str = Field(default="INFO")
    max_messages_per_hour: int = Field(default=20)
    max_messages_per_day: int = Field(default=100)
    
    # Jitter Algorithm - Activity State
    active_session_mean_minutes: int = Field(default=20)
    active_session_stddev_minutes: int = Field(default=10)
    idle_session_mean_minutes: int = Field(default=75)
    idle_session_stddev_minutes: int = Field(default=30)
    
    # Jitter Algorithm - Timing
    base_wpm: int = Field(default=38, description="Base words per minute")
    typing_variance: float = Field(default=0.30, description="30% variance")
    thinking_mean_seconds: float = Field(default=8.0)
    thinking_stddev_seconds: float = Field(default=12.0)
    
    # Jitter Algorithm - Constraints
    min_gap_urgent_seconds: int = Field(default=5)
    min_gap_high_seconds: int = Field(default=30)
    min_gap_normal_seconds: int = Field(default=60)
    min_gap_low_seconds: int = Field(default=120)
    
    # Message Constraints
    max_message_length: int = Field(default=160, description="SMS length limit")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()

