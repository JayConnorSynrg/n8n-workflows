"""Configuration management with validation."""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # LiveKit
    livekit_url: str = Field(..., alias="LIVEKIT_URL")
    livekit_api_key: str = Field(..., alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(..., alias="LIVEKIT_API_SECRET")

    # Deepgram
    deepgram_api_key: str = Field(..., alias="DEEPGRAM_API_KEY")
    deepgram_model: str = Field(default="nova-3", alias="DEEPGRAM_MODEL")

    # Fireworks AI (LLM - function calling + large context)
    # IMPORTANT: Only use models with function calling support on Fireworks.
    # llama-v3p3-70b-instruct does NOT support function calling on Fireworks!
    # Models with FC: deepseek-v3p1 (163K, fastest TTFT)
    #                 llama4-scout-instruct-basic (1M ctx, cheapest)
    #                 llama-v3p1-70b-instruct (131K, battle-tested)
    #                 kimi-k2-instruct-0905 (262K, agentic)
    fireworks_api_key: str = Field(default="", alias="FIREWORKS_API_KEY")
    fireworks_model: str = Field(
        default="accounts/fireworks/models/deepseek-v3p1",
        alias="FIREWORKS_MODEL"
    )
    fireworks_temperature: float = Field(default=0.6, alias="FIREWORKS_TEMPERATURE")
    fireworks_max_tokens: int = Field(default=512, alias="FIREWORKS_MAX_TOKENS")

    # Cartesia
    cartesia_api_key: str = Field(..., alias="CARTESIA_API_KEY")
    cartesia_model: str = Field(default="sonic-3", alias="CARTESIA_MODEL")
    cartesia_voice: str = Field(
        default="a167e0f3-df7e-4d52-a9c3-f949145efdab",  # Confirmed working voice
        alias="CARTESIA_VOICE"
    )

    # n8n Integration
    n8n_webhook_base_url: str = Field(
        default="https://jayconnorexe.app.n8n.cloud/webhook",
        alias="N8N_WEBHOOK_BASE_URL"
    )

    # Agent Settings
    agent_name: str = Field(default="Voice Assistant", alias="AGENT_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Composio Integration (SDK-only execution via composioBatchExecute/composioExecute)
    composio_api_key: str = Field(default="", alias="COMPOSIO_API_KEY")
    composio_base_url: str = Field(
        default="https://backend.composio.dev/api",
        alias="COMPOSIO_BASE_URL"
    )
    composio_user_id: str = Field(default="", alias="COMPOSIO_USER_ID")

    @field_validator("livekit_url")
    @classmethod
    def validate_livekit_url(cls, v: str) -> str:
        if not v.startswith("wss://"):
            raise ValueError("LIVEKIT_URL must start with wss://")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"  # Allow extra env vars (Railway adds its own)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
