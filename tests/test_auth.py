"""Tests for AuthManager and AuthConfig."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.auth import AuthManager, AuthConfig, CredsStatus, get_auth_manager, set_auth_manager


def test_auth_config_from_env_empty():
    """AuthConfig.from_env with no env vars uses defaults."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = AuthConfig.from_env()
    assert cfg.region == "us-east-1"
    assert cfg.aws_access_key_id is None
    assert cfg.aws_profile is None


def test_auth_config_from_env_keys():
    """AuthConfig.from_env reads AWS_* env vars."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "AKIA",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "token",
            "AWS_REGION": "eu-west-1",
        },
        clear=False,
    ):
        cfg = AuthConfig.from_env()
    assert cfg.aws_access_key_id == "AKIA"
    assert cfg.aws_secret_access_key == "secret"
    assert cfg.aws_session_token == "token"
    assert cfg.region == "eu-west-1"


def test_auth_manager_build_session_env(auth_config_env):
    """AuthManager with env keys builds session without profile."""
    manager = AuthManager(config=auth_config_env)
    session = manager._build_session()
    assert session is not None
    creds = session.get_credentials()
    assert creds is not None
    frozen = creds.get_frozen_credentials()
    assert frozen.access_key == auth_config_env.aws_access_key_id


def test_auth_manager_get_client_creates_once(auth_config_env):
    """get_client returns same client when already created."""
    with patch("src.auth.boto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        manager = AuthManager(config=auth_config_env)
        c1 = manager.get_client()
        c2 = manager.get_client()
        assert c1 is c2 is mock_client
        mock_session.client.assert_called_once()


def test_auth_manager_refresh_credentials_recreates_client(auth_config_env):
    """refresh_credentials clears client and recreates on next get_client."""
    with patch("src.auth.boto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        manager = AuthManager(config=auth_config_env)
        manager.get_client()
        manager.refresh_credentials()
        manager.get_client()
        assert mock_session.client.call_count >= 2


def test_auth_manager_switch_profile(auth_config_env):
    """switch_profile sets profile and clears env key state."""
    manager = AuthManager(config=auth_config_env)
    manager._client = MagicMock()
    manager._session = MagicMock()
    manager.switch_profile("other-profile")
    assert manager._config.aws_profile == "other-profile"
    assert manager._config.aws_access_key_id is None
    assert manager._config.aws_secret_access_key is None
    assert manager._client is None


def test_auth_manager_list_profiles_empty_file():
    """list_profiles returns [] when credentials file does not exist."""
    manager = AuthManager(config=AuthConfig())
    with patch.object(manager, "_get_credentials_path", return_value="/nonexistent/path"):
        profiles = manager.list_profiles()
    assert profiles == []


def test_auth_manager_list_profiles_parses_ini(tmp_path):
    """list_profiles parses [profile] sections from credentials file."""
    creds_file = tmp_path / "credentials"
    creds_file.write_text("[default]\nkey=value\n[profile dev]\n[profile prod]\n")
    manager = AuthManager(config=AuthConfig())
    with patch.object(manager, "_get_credentials_path", return_value=str(creds_file)):
        profiles = manager.list_profiles()
    # default is excluded per AuthManager.list_profiles
    assert "dev" in profiles
    assert "prod" in profiles


def test_auth_manager_get_creds_status_with_env(auth_manager_with_mock_client):
    """get_creds_status returns valid status when session has credentials."""
    manager = auth_manager_with_mock_client
    mock_creds = MagicMock()
    mock_creds.get_frozen_credentials.return_value = MagicMock(access_key="AKIA12345678")
    manager._session.get_credentials.return_value = mock_creds
    status = manager.get_creds_status()
    assert status.valid is True
    assert status.source == "env"
    assert status.access_key_id_prefix == "AKIA1234..."


def test_get_auth_manager_singleton():
    """get_auth_manager returns same instance until set_auth_manager(None)."""
    set_auth_manager(None)
    m1 = get_auth_manager()
    m2 = get_auth_manager()
    assert m1 is m2
    set_auth_manager(None)
