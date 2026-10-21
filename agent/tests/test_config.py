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
    assert settings.agent_max_pages_per_cycle == 10
    assert settings.max_pages_per_cycle == 10
    assert settings.state_db_path.name == "agent_state.db"
    assert settings.lock_file_path.name == "agent.lock"
    assert settings.log_file_path.name == "agent.log"
    assert settings.cloud_api_verify_ssl is True
    assert settings.agent_clamp_negative_balance is False


def test_tls_verification_across_all_environments() -> None:
    # Production HTTPS
    prod = AgentSettings(
        agent_env="production",
        agent_cloud_base_url="https://cloud.example.com",
        agent_api_key="a" * 20,
    )
    assert prod.cloud_api_verify_ssl is True

    # Development HTTPS
    dev = AgentSettings(
        agent_env="development",
        agent_cloud_base_url="https://dev-cloud.example.com",
        agent_api_key="a" * 20,
    )
    assert dev.cloud_api_verify_ssl is True

    # Test HTTPS
    test = AgentSettings(
        agent_env="test",
        agent_cloud_base_url="https://test-cloud.example.com",
        agent_api_key="a" * 20,
    )
    assert test.cloud_api_verify_ssl is True


def test_no_verify_false_in_agent_source() -> None:
    """Regression check: Agent source code must never contain verify=False."""
    src_dir = Path(__file__).parent.parent / "src"
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "verify=False" not in content, f"Found verify=False in {py_file}"
        assert "verify = False" not in content, f"Found verify = False in {py_file}"


def test_retry_backoff_bounds_validation() -> None:
    # max < initial raises ValidationError
    with pytest.raises(ValidationError, match="must be >= AGENT_SYNC_BACKOFF_INITIAL_SECONDS"):
        AgentSettings(
            agent_api_key="test-api-key",
            agent_sync_backoff_initial_seconds=10.0,
            agent_sync_backoff_max_seconds=5.0,
        )

    # Valid custom backoff
    settings = AgentSettings(
        agent_api_key="test-api-key",
        agent_sync_backoff_initial_seconds=1.5,
        agent_sync_backoff_max_seconds=120.0,
        agent_sync_backoff_jitter_ratio=0.1,
    )
    assert settings.sync_backoff_initial_seconds == 1.5
    assert settings.sync_backoff_max_seconds == 120.0
    assert settings.sync_backoff_jitter_ratio == 0.1


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


def test_one_adapter_config(tmp_path: Path) -> None:
    settings = AgentSettings(agent_api_key="test-api-key-123456")
    assert settings.agent_one_timezone == "Asia/Almaty"
    assert settings.one_timezone == "Asia/Almaty"
    assert settings.agent_one_lookback_days == 3
    assert settings.lookback_days == 3
    assert settings.dry_run is False
    assert settings.mapping_path.name == "stage0_mapping.json"
    assert settings.state_key_path.name == "agent_state.key"


def test_com_mode_in_production_requires_valid_mapping(tmp_path: Path) -> None:
    # Missing mapping file
    with pytest.raises(ValidationError, match="Valid ONE_MAPPING_PATH"):
        AgentSettings(
            agent_env="production",
            agent_cloud_base_url="https://cloud.example.com",
            agent_api_key="a" * 20,
            one_adapter_mode="com",
            one_connection_string="Srvr=1c;Ref=base;",
            one_mapping_path=tmp_path / "nonexistent.json",
        )

    # Existing mapping file
    valid_file = tmp_path / "mapping.json"
    valid_file.write_text("{}", encoding="utf-8")
    settings = AgentSettings(
        agent_env="production",
        agent_cloud_base_url="https://cloud.example.com",
        agent_api_key="a" * 20,
        one_adapter_mode="com",
        one_connection_string="Srvr=1c;Ref=base;",
        one_mapping_path=valid_file,
    )
    assert settings.mapping_path == valid_file

