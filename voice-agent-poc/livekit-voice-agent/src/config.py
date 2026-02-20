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

    # LLM Provider Selection: "fireworks" (default) or "cerebras"
    # Fireworks AI: 128K context, reliable tool calling, OpenAI-compatible
    # Cerebras: Fast inference but limited context (8K-65K depending on model)
    llm_provider: str = Field(default="fireworks", alias="LLM_PROVIDER")

    # Fireworks AI (Primary LLM - function calling + large context)
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

    # Cerebras LLM (Fallback - 1M free tokens/day, ~1000 TPS)
    # Production models: gpt-oss-120b (65K ctx), llama3.1-8b (8K ctx)
    # llama-3.3-70b was deprecated 2026-02-16
    cerebras_api_key: str = Field(default="", alias="CEREBRAS_API_KEY")
    cerebras_model: str = Field(default="gpt-oss-120b", alias="CEREBRAS_MODEL")
    cerebras_fallback_model: str = Field(default="gpt-oss-120b", alias="CEREBRAS_FALLBACK_MODEL")
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

    # Composio Tool Router (meta-tool MCP — on-demand tool discovery)
    # LLM gets meta-tools (search, execute) instead of individual action schemas.
    # Configure available tools via Composio dashboard, not in code.
    composio_api_key: str = Field(default="", alias="COMPOSIO_API_KEY")
    composio_router_enabled: bool = Field(default=True, alias="COMPOSIO_ROUTER_ENABLED")
    composio_user_id: str = Field(default="", alias="COMPOSIO_USER_ID")

    # Direct MCP URL (fallback — only used if COMPOSIO_ROUTER_ENABLED=false)
    mcp_server_url: str = Field(default="", alias="MCP_SERVER_URL")

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
