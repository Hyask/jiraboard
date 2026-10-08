from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://warthogs.atlassian.net"
DEFAULT_TOKEN_FILE = ".jira-token"


class ConfigError(RuntimeError):
    """Raised when the Jira credentials or configuration are unusable."""


def resolve_base_url(base_url: str | None = None) -> str:
    """Return the Jira site URL: explicit, then ``JIRA_BASE_URL``, then default."""
    return (base_url or os.environ.get("JIRA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


@dataclass(frozen=True)
class JiraConfig:
    """Everything needed to talk to Jira and render a report."""

    base_url: str
    email: str
    api_token: str
    task_key: str
    output: Path

    @classmethod
    def load(
        cls,
        task_key: str,
        output: Path,
        base_url: str | None = None,
        token_file: str | None = None,
    ) -> "JiraConfig":
        email, api_token = read_credentials(token_file)
        resolved_base = resolve_base_url(base_url)
        return cls(
            base_url=resolved_base,
            email=email,
            api_token=api_token,
            task_key=task_key.strip().upper(),
            output=Path(output),
        )


def read_credentials(token_file: str | None = None) -> tuple[str, str]:
    """Return ``(email, api_token)``.

    Credentials are read from the ``JIRA_EMAIL``/``JIRA_API_TOKEN`` environment
    variables when both are set, otherwise from the token file whose single line
    is formatted ``email:api_token``.
    """
    env_email = os.environ.get("JIRA_EMAIL")
    env_token = os.environ.get("JIRA_API_TOKEN")
    if env_email and env_token:
        return env_email, env_token

    path = Path(token_file or os.environ.get("JIRA_TOKEN_FILE", DEFAULT_TOKEN_FILE))
    if not path.is_file():
        raise ConfigError(f"token file not found: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ConfigError(f"token file is empty: {path}")
    if ":" not in raw:
        raise ConfigError(
            f"token file must contain a single 'email:api_token' line: {path}"
        )

    email, api_token = raw.split(":", 1)
    email, api_token = email.strip(), api_token.strip()
    if not email or not api_token:
        raise ConfigError(f"token file has an empty email or token: {path}")
    return email, api_token
