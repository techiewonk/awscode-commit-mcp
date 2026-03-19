"""AuthManager: env / profile / default chain; single CodeCommit client for all services."""

import os
import re
from dataclasses import dataclass, field
from typing import Any

import boto3
import botocore.session
from botocore.credentials import Credentials
from botocore.exceptions import ClientError


@dataclass
class AuthConfig:
    """AWS config from environment; priority: env keys > profile > default chain."""

    aws_profile: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region: str = "us-east-1"
    credentials_file: str | None = None
    config_file: str | None = None

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls(
            aws_profile=os.environ.get("AWS_PROFILE") or None,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
            region=os.environ.get("AWS_REGION") or "us-east-1",
            credentials_file=os.environ.get("AWS_CREDENTIALS_FILE") or None,
            config_file=os.environ.get("AWS_CONFIG_FILE") or None,
        )


@dataclass
class CredsStatus:
    """Current credentials status for aws_creds_status tool."""

    valid: bool
    source: str  # "env" | "profile" | "default"
    profile: str | None = None
    access_key_id_prefix: str | None = None
    expiration: str | None = None
    message: str = ""


class AuthManager:
    """Single AuthManager → one boto3 CodeCommit client; all services use it."""

    def __init__(self, config: AuthConfig | None = None):
        self._config = config or AuthConfig.from_env()
        self._client: Any = None
        self._session: botocore.session.Session | None = None

    def _get_credentials_path(self) -> str:
        if self._config.credentials_file and os.path.isfile(self._config.credentials_file):
            return self._config.credentials_file
        default = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
        return default if os.path.isfile(default) else default

    def _build_session(self) -> botocore.session.Session:
        if self._config.aws_access_key_id and self._config.aws_secret_access_key:
            return botocore.session.Session(
                aws_access_key_id=self._config.aws_access_key_id,
                aws_secret_access_key=self._config.aws_secret_access_key,
                aws_session_token=self._config.aws_session_token,
                region_name=self._config.region,
            )
        if self._config.aws_profile:
            return boto3.Session(
                profile_name=self._config.aws_profile,
                region_name=self._config.region,
            )
        return boto3.Session(region_name=self._config.region)

    def _create_client(self):
        session = self._build_session()
        self._session = session
        self._client = session.client("codecommit", region_name=self._config.region)
        return self._client

    def get_client(self):
        """Return CodeCommit client; create or refresh if needed."""
        if self._client is None:
            return self._create_client()
        # Optional: check expiry for profile/assumed role and refresh
        return self._client

    def refresh_credentials(self) -> None:
        """Reload credentials from configured source; recreate client."""
        self._client = None
        self._session = None
        self._create_client()

    def switch_profile(self, profile_name: str) -> None:
        """Switch to a named profile; clear env-key state and recreate client."""
        self._config.aws_profile = profile_name
        self._config.aws_access_key_id = None
        self._config.aws_secret_access_key = None
        self._config.aws_session_token = None
        self._client = None
        self._session = None
        self._create_client()

    def list_profiles(self) -> list[str]:
        """List profile names from ~/.aws/credentials (or AWS_CREDENTIALS_FILE)."""
        path = self._get_credentials_path()
        if not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return []
        profiles = re.findall(r"^\[([^\]]+)\]", content, re.MULTILINE)
        return [p.strip() for p in profiles if p.strip() != "default"]

    def get_creds_status(self) -> CredsStatus:
        """Return current credentials status (validity, source, key prefix, expiration)."""
        try:
            creds = self._session.get_credentials() if self._session else None
            if creds is None and self._client is None:
                self._create_client()
            creds = (self._session or self._build_session()).get_credentials()
            if creds is None:
                return CredsStatus(
                    valid=False,
                    source="none",
                    message="No credentials resolved",
                )
            frozen = creds.get_frozen_credentials()
            key = frozen.access_key if frozen else None
            source = "env" if (self._config.aws_access_key_id) else ("profile" if self._config.aws_profile else "default")
            expiration = getattr(creds, "expiry", None) or getattr(creds, "expiration", None)
            exp_str = str(expiration) if expiration else None
            return CredsStatus(
                valid=True,
                source=source,
                profile=self._config.aws_profile,
                access_key_id_prefix=key[:8] + "..." if key and len(key) >= 8 else None,
                expiration=exp_str,
                message="Credentials valid",
            )
        except Exception as e:
            return CredsStatus(
                valid=False,
                source="none",
                message=str(e),
            )


# Singleton used by tools; set after first get or explicit init
_auth_manager: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager(AuthConfig.from_env())
    return _auth_manager


def set_auth_manager(manager: AuthManager | None) -> None:
    global _auth_manager
    _auth_manager = manager
