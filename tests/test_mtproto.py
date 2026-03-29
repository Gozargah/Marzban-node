from pathlib import Path
from unittest.mock import patch

import pytest

import mtproto


def _patch_mtproto(**overrides):
    defaults = {
        "MTPROTO_ENABLED": True,
        "MTPROTO_DOMAIN": "tg.example.com",
        "MTPROTO_PORT": 1443,
        "MTPROTO_MODE": "dd",
        "MTPROTO_USE_MIDDLE_PROXY": True,
        "MTPROTO_LISTEN_ADDR_IPV4": "0.0.0.0",
        "MTPROTO_IPV6_ENABLED": False,
        "MTPROTO_NETWORK_PREFER": 4,
        "MTPROTO_SHOW_LINKS": False,
        "MTPROTO_LOG_LEVEL": "normal",
        "MTPROTO_RUST_LOG": "info,telemt::links=warn",
        "MTPROTO_RELOAD_INTERVAL": 5,
        "MTPROTO_PROCESS_RESTART_DELAY_MS": 1000,
        "MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS": 3,
        "MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS": 250,
        "MTPROTO_UPSTREAM_CONNECT_BUDGET_MS": 25000,
        "MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD": 3,
        "MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS": False,
        "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT": 25,
        "MTPROTO_TG_CONNECT_TIMEOUT": 20,
        "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT": 60,
        "MTPROTO_CLIENT_ACK_TIMEOUT": 300,
        "MTPROTO_TLS_DOMAIN": "",
    }
    defaults.update(overrides)
    return patch.multiple("mtproto", **defaults)


def test_render_mtproto_config_uses_domain_links():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15,
        MTPROTO_TG_CONNECT_TIMEOUT=10,
    ):
        rendered = mtproto.render_mtproto_config(users)

    assert "[general.links]" in rendered
    assert 'log_level = "normal"' in rendered
    assert "upstream_connect_retry_attempts = 3" in rendered
    assert "upstream_connect_retry_backoff_ms = 250" in rendered
    assert "upstream_connect_budget_ms = 25000" in rendered
    assert "upstream_unhealthy_fail_threshold = 3" in rendered
    assert "upstream_connect_failfast_hard_errors = false" in rendered
    assert "show = []" in rendered
    assert 'public_host = "tg.example.com"' in rendered
    assert "public_port = 1443" in rendered
    assert "use_middle_proxy = true" in rendered
    assert "[network]" in rendered
    assert "ipv4 = true" in rendered
    assert "ipv6 = false" in rendered
    assert "prefer = 4" in rendered
    assert 'listen_addr_ipv4 = "0.0.0.0"' in rendered
    assert "[timeouts]" in rendered
    assert "client_handshake = 15" in rendered
    assert "tg_connect = 10" in rendered
    assert "client_keepalive = 60" in rendered
    assert "client_ack = 300" in rendered
    assert '"alice" = "0123456789abcdef0123456789abcdef"' in rendered


def test_render_mtproto_config_requires_tls_domain_for_ee():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(MTPROTO_PORT=443, MTPROTO_MODE="ee", MTPROTO_TLS_DOMAIN=""):
        with pytest.raises(ValueError, match="MTPROTO_TLS_DOMAIN"):
            mtproto.render_mtproto_config(users)


def test_apply_mtproto_users_writes_config(tmp_path: Path):
    path = tmp_path / "telemt.toml"
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(
        MTPROTO_CONFIG_PATH=str(path),
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15,
        MTPROTO_TG_CONNECT_TIMEOUT=10,
    ):
        status = mtproto.apply_mtproto_users(users)

    assert path.exists()
    assert status["enabled"] is True
    assert status["configured_users"] == 1
    assert 'public_host = "tg.example.com"' in path.read_text(encoding="utf-8")


def test_render_mtproto_config_requires_supported_network_prefer():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(MTPROTO_NETWORK_PREFER=5):
        with pytest.raises(ValueError, match="MTPROTO_NETWORK_PREFER"):
            mtproto.render_mtproto_config(users)


def test_render_mtproto_config_requires_supported_log_level():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(MTPROTO_LOG_LEVEL="info"):
        with pytest.raises(ValueError, match="MTPROTO_LOG_LEVEL"):
            mtproto.render_mtproto_config(users)


def test_render_mtproto_config_requires_budget_not_less_than_tg_connect():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(
        MTPROTO_TG_CONNECT_TIMEOUT=20,
        MTPROTO_UPSTREAM_CONNECT_BUDGET_MS=15000,
    ):
        with pytest.raises(ValueError, match="MTPROTO_UPSTREAM_CONNECT_BUDGET_MS"):
            mtproto.render_mtproto_config(users)


def test_render_mtproto_config_requires_handshake_not_less_than_tg_connect():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with _patch_mtproto(
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=10,
        MTPROTO_TG_CONNECT_TIMEOUT=20,
    ):
        with pytest.raises(ValueError, match="MTPROTO_CLIENT_HANDSHAKE_TIMEOUT"):
            mtproto.render_mtproto_config(users)


def test_get_mtproto_status_exposes_effective_runtime(tmp_path: Path):
    path = tmp_path / "telemt.toml"
    path.write_text("ok", encoding="utf-8")

    with _patch_mtproto(
        MTPROTO_USE_MIDDLE_PROXY=False,
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15,
        MTPROTO_TG_CONNECT_TIMEOUT=10,
        MTPROTO_CONFIG_PATH=str(path),
    ):
        status = mtproto.get_mtproto_status(configured_users=7)

    assert status == {
        "enabled": True,
        "domain": "tg.example.com",
        "port": 1443,
        "mode": "dd",
        "tls_domain": "",
        "use_middle_proxy": False,
        "runtime_profile": "single-node-resilient-direct",
        "show_links": False,
        "log_level": "normal",
        "rust_log": "info,telemt::links=warn",
        "listen_addr_ipv4": "0.0.0.0",
        "ipv6_enabled": False,
        "network_prefer": 4,
        "reload_strategy": "telemt_internal_hot_reload",
        "reload_interval": 5,
        "process_restart_delay_ms": 1000,
        "upstream_connect_retry_attempts": 3,
        "upstream_connect_retry_backoff_ms": 250,
        "upstream_connect_budget_ms": 25000,
        "upstream_unhealthy_fail_threshold": 3,
        "upstream_connect_failfast_hard_errors": False,
        "client_handshake_timeout": 15,
        "tg_connect_timeout": 10,
        "client_keepalive_timeout": 60,
        "client_ack_timeout": 300,
        "config_path": str(path),
        "config_exists": True,
        "configured_users": 7,
    }
