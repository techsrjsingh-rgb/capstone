"""
Central configuration for the Fraud Detection AI Agent.
All settings are read from environment variables (see .env.example).
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    # ── Anthropic API ──────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Primary model for complex reasoning; fallback is cheaper/faster
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "claude-opus-4-8")
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "claude-sonnet-4-6")

    # ── Agent settings ─────────────────────────────────────────────
    MAX_TOKENS: int = 4096
    THINKING_BUDGET: int = 5000   # tokens for extended thinking (Autonomous Planning)
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0  # seconds; doubled on each retry

    # ── MCP server ports ───────────────────────────────────────────
    FRAUD_MCP_PORT: int = int(os.getenv("FRAUD_MCP_PORT", "8002"))
    GEO_MCP_PORT: int = int(os.getenv("GEO_MCP_PORT", "8003"))

    # ── Fraud detection thresholds ─────────────────────────────────
    HIGH_AMOUNT_THRESHOLD: float = 100000.0   # ₹1,00,000
    RAPID_TXN_WINDOW_SEC: int = 300           # 5 minutes
    RAPID_TXN_COUNT: int = 3                  # 3+ transactions = rapid

    # Known high-fraud-risk location names (simplified)
    FRAUD_LOCATIONS: list = [
        "nigeria", "lagos", "abuja", "unknown", "anonymous",
        "offshore", "cayman", "panama", "dark web",
    ]

    # Countries considered "international" for a domestic Indian bank
    DOMESTIC_COUNTRY: str = "india"

    # ── Governance ─────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 20   # max requests per minute
    AUDIT_LOG_FILE: str = "audit.jsonl"


config = Config()
