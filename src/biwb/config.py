"""Runtime configuration read from environment variables (optionally via a git-ignored .env file).

Secrets are never read into this object: the Anthropic SDK reads ANTHROPIC_API_KEY itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_TRUE = {"1", "true", "yes", "on"}
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class Settings:
    workspace: Path
    ai_enabled: bool
    ai_model: str
    ai_effort: str

    @property
    def app_db_path(self) -> Path:
        return self.workspace / "app.db"

    @property
    def projects_dir(self) -> Path:
        return self.workspace / "projects"


def load_settings(env: dict[str, str] | None = None, *, use_dotenv: bool = True) -> Settings:
    """Build Settings from `env` (defaults to os.environ). Invalid values fail loudly."""
    if env is None:
        if use_dotenv:
            load_dotenv(override=False)
        env = dict(os.environ)

    effort = env.get("BIWB_AI_EFFORT", "medium").strip().lower()
    if effort not in VALID_EFFORTS:
        raise ValueError(f"BIWB_AI_EFFORT must be one of {VALID_EFFORTS}, got {effort!r}")

    model = env.get("BIWB_AI_MODEL", "claude-opus-5-5").strip()
    if not model:
        raise ValueError("BIWB_AI_MODEL must not be empty")

    return Settings(
        workspace=Path(env.get("BIWB_WORKSPACE", "./workspace")).resolve(),
        ai_enabled=env.get("BIWB_AI_ENABLED", "false").strip().lower() in _TRUE,
        ai_model=model,
        ai_effort=effort,
    )
