from pathlib import Path
from unittest.mock import patch

import pytest

import mtproto


def test_render_mtproto_config_uses_domain_links():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with patch("mtproto.MTPROTO_ENABLED", True), patch(
        "mtproto.MTPROTO_DOMAIN", "tg.example.com"
    ), patch("mtproto.MTPROTO_PORT", 1443), patch("mtproto.MTPROTO_MODE", "dd"):
        rendered = mtproto.render_mtproto_config(users)

    assert "[general.links]" in rendered
    assert 'public_host = "tg.example.com"' in rendered
    assert "public_port = 1443" in rendered
    assert '"alice" = "0123456789abcdef0123456789abcdef"' in rendered


def test_render_mtproto_config_requires_tls_domain_for_ee():
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with patch("mtproto.MTPROTO_ENABLED", True), patch(
        "mtproto.MTPROTO_DOMAIN", "tg.example.com"
    ), patch("mtproto.MTPROTO_PORT", 443), patch("mtproto.MTPROTO_MODE", "ee"), patch(
        "mtproto.MTPROTO_TLS_DOMAIN", ""
    ):
        with pytest.raises(ValueError, match="MTPROTO_TLS_DOMAIN"):
            mtproto.render_mtproto_config(users)


def test_apply_mtproto_users_writes_config(tmp_path: Path):
    path = tmp_path / "telemt.toml"
    users = [{"username": "alice", "secret": "0123456789abcdef0123456789abcdef"}]

    with patch("mtproto.MTPROTO_ENABLED", True), patch(
        "mtproto.MTPROTO_DOMAIN", "tg.example.com"
    ), patch("mtproto.MTPROTO_PORT", 1443), patch("mtproto.MTPROTO_MODE", "dd"), patch(
        "mtproto.MTPROTO_CONFIG_PATH", str(path)
    ):
        status = mtproto.apply_mtproto_users(users)

    assert path.exists()
    assert status["enabled"] is True
    assert status["configured_users"] == 1
    assert 'public_host = "tg.example.com"' in path.read_text(encoding="utf-8")
