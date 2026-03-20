"""Pytest configuration and shared fixtures."""

from unittest.mock import MagicMock

import pytest

from src.auth import AuthConfig, AuthManager, set_auth_manager


@pytest.fixture
def mock_codecommit_client():
    """Mock boto3 CodeCommit client for service tests."""
    client = MagicMock()
    return client


@pytest.fixture
def auth_config_env():
    """AuthConfig with env keys (no profile)."""
    return AuthConfig(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_session_token=None,
        region="us-east-1",
    )


@pytest.fixture
def auth_config_profile():
    """AuthConfig with profile only."""
    return AuthConfig(
        aws_profile="test-profile",
        region="us-east-2",
    )


@pytest.fixture
def auth_manager_with_mock_client(mock_codecommit_client, auth_config_env):
    """AuthManager that returns a fixed mock client (no real boto3)."""
    manager = AuthManager(config=auth_config_env)
    manager._client = mock_codecommit_client
    manager._session = MagicMock()
    return manager


@pytest.fixture(autouse=True)
def reset_auth_manager_after_test():
    """Reset global auth manager after each test to avoid leakage."""
    yield
    set_auth_manager(None)
