"""Configuração lida das variáveis de ambiente (ou de um arquivo .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _id_list(name: str) -> set[int]:
    raw = os.getenv(name, "")
    return {int(part) for part in raw.replace(" ", "").split(",") if part}


@dataclass(frozen=True)
class Config:
    discord_token: str
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    allowed_role_ids: set[int] = field(default_factory=set)
    require_confirmation: bool = True
    confirm_timeout: int = 60
    max_tool_rounds: int = 25
    max_history_messages: int = 80
    dev_guild_id: int | None = None

    @property
    def use_fallbacks(self) -> bool:
        # Fallback no servidor quando o modelo recusa um pedido. O Haiku não
        # tem fallback no servidor, então não enviamos o parâmetro para ele.
        return not self.model.startswith("claude-haiku")

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise SystemExit("Defina DISCORD_TOKEN no ambiente ou no arquivo .env")

        effort = os.getenv("CLAUDE_EFFORT", "medium").strip().lower()
        if effort not in VALID_EFFORTS:
            raise SystemExit(f"CLAUDE_EFFORT inválido: {effort!r} (use {sorted(VALID_EFFORTS)})")

        dev_guild = os.getenv("DEV_GUILD_ID", "").strip()
        return cls(
            discord_token=token,
            model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5").strip() or "claude-opus-5-5",
            effort=effort,
            allowed_role_ids=_id_list("ALLOWED_ROLE_IDS"),
            require_confirmation=_bool("REQUIRE_CONFIRMATION", True),
            confirm_timeout=_int("CONFIRM_TIMEOUT_SECONDS", 60),
            max_tool_rounds=_int("MAX_TOOL_ROUNDS", 25),
            max_history_messages=_int("MAX_HISTORY_MESSAGES", 80),
            dev_guild_id=int(dev_guild) if dev_guild else None,
        )
