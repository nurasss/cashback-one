"""Tests for AgentSettings configuration and validations."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from poscenter_loyalty_agent.config import AgentSettings


def test_default_settings() -> None:
    settings = AgentSettings(agent_api_key="test-key-12345678")
    assert settings.agent_env == "development"
    assert settings.agent_cloud_base_url == "http://localhost:8000"
    assert settings.one_adapter_mode == "stub"
    assert settings.agent_card_batch_size == 100
    assert settings.agent_tx_batch_size == 200
    assert settings.state_db_path.name == "agent_state.db"
    assert settings.lock_file_path.name == "agent.lock"
    assert settings.log_file_path.name == "agent.log"


def test_production_validations() -> None:
    # Production requires HTTPS
    with pytest.raises(ValidationError, match="HTTPS"):
        AgentSettings(
            agent_env="production",
            agent_cloud_base_url="http://cloud.example.com",
            agent_api_key="a" * 20,
        )

    # Production requires API key >= 16 chars
    with pytest.raises(ValidationError, match="at least 16 characters"):
        AgentSettings(
            agent_env="production",
            agent_cloud_base_url="https://cloud.example.com",
            agent_api_key="short",
        )

    # Fake mode forbidden in production
    with pytest.raises(ValidationError, match="strictly forbidden"):
        AgentSettings(
            agent_env="production",
            agent_cloud_base_url="https://cloud.example.com",
            agent_api_key="a" * 20,
            one_adapter_mode="fake",
        )


def test_fake_mode_allowed_in_test() -> None:
    settings = AgentSettings(
        agent_env="test",
        agent_cloud_base_url="http://localhost:8000",
        agent_api_key="test-api-key-value",
        one_adapter_mode="fake",
    )
    assert settings.one_adapter_mode == "fake"


def test_com_mode_in_production_requires_connection_string() -> None:
    with pytest.raises(ValidationError, match="ONE_CONNECTION_STRING is required"):
        AgentSettings(
            agent_env="production",
            agent_cloud_base_url="https://cloud.example.com",
            agent_api_key="a" * 20,
            one_adapter_mode="com",
            one_connection_string="",
        )


def test_custom_paths() -> None:
    db_path = Path("/tmp/custom_state.db")
    log_dir = Path("/tmp/custom_logs")
    settings = AgentSettings(
        agent_api_key="custom-key-12345",
        agent_state_db_path=db_path,
        agent_log_dir=log_dir,
    )
    assert settings.state_db_path == db_path
    assert settings.lock_file_path == Path("/tmp/agent.lock")
    assert settings.log_file_path == log_dir / "agent.log"
