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

    # Cerebras LLM (1M free tokens/day, ~1000 TPS)
    # Note: llama-3.3-70b has better function calling support than 8b
    cerebras_api_key: str = Field(..., alias="CEREBRAS_API_KEY")
    cerebras_model: str = Field(default="llama-3.3-70b", alias="CEREBRAS_MODEL")
    cerebras_temperature: float = Field(default=0.6, alias="CEREBRAS_TEMPERATURE")
    cerebras_max_tokens: int = Field(default=150, alias="CEREBRAS_MAX_TOKENS")

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

    # MCP Integration (Native LiveKit MCP - replaces Composio LangChain SDK)
    # Set MCP_SERVER_URL to your MCP endpoint to enable native tool auto-discovery.
    # Leave empty to run with only ASYNC_TOOLS (n8n webhooks) - graceful degradation.
    # Example: https://backend.composio.dev/v3/mcp/{id}/mcp?user_id={uid}
    mcp_server_url: str = Field(default="", alias="MCP_SERVER_URL")

    # Composio Integration (kept for reference - credentials now consumed via MCP endpoint)
    # These are no longer read by the agent directly; the MCP_SERVER_URL handles auth.
    composio_api_key: str = Field(default="", alias="COMPOSIO_API_KEY")
    composio_toolkits: str = Field(default="", alias="COMPOSIO_TOOLKITS")
    composio_user_id: str = Field(default="default", alias="COMPOSIO_USER_ID")

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
