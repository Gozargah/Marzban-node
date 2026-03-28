from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from config import (
    MTPROTO_CLIENT_ACK_TIMEOUT,
    MTPROTO_CLIENT_HANDSHAKE_TIMEOUT,
    MTPROTO_CLIENT_KEEPALIVE_TIMEOUT,
    MTPROTO_CONFIG_PATH,
    MTPROTO_DOMAIN,
    MTPROTO_ENABLED,
    MTPROTO_IPV6_ENABLED,
    MTPROTO_LISTEN_ADDR_IPV4,
    MTPROTO_LOG_LEVEL,
    MTPROTO_MODE,
    MTPROTO_NETWORK_PREFER,
    MTPROTO_PORT,
    MTPROTO_RELOAD_INTERVAL,
    MTPROTO_RUST_LOG,
    MTPROTO_SHOW_LINKS,
    MTPROTO_TG_CONNECT_TIMEOUT,
    MTPROTO_TLS_DOMAIN,
    MTPROTO_USE_MIDDLE_PROXY,
)
from logger import logger


def mtproto_enabled() -> bool:
    return bool(MTPROTO_ENABLED)


def _quoted_toml(value: str) -> str:
    return json.dumps(value)


def _bool_toml(value: bool) -> str:
    return "true" if value else "false"


def _secret_mode() -> str:
    mode = MTPROTO_MODE.lower().strip()
    if mode not in {"dd", "ee"}:
        raise ValueError("MTPROTO_MODE must be either 'dd' or 'ee'")
    return mode


def _tls_domain() -> str:
    domain = MTPROTO_TLS_DOMAIN.strip()
    if not domain:
        raise ValueError("MTPROTO_TLS_DOMAIN must be set when MTPROTO_MODE=ee")
    return domain


def _runtime_domain() -> str:
    domain = MTPROTO_DOMAIN.strip()
    if not domain:
        raise ValueError("MTPROTO_DOMAIN must be set when MTPROTO_ENABLED=true")
    return domain


def _listen_addr_ipv4() -> str:
    listen_addr = MTPROTO_LISTEN_ADDR_IPV4.strip()
    if not listen_addr:
        raise ValueError("MTPROTO_LISTEN_ADDR_IPV4 must be set when MTPROTO_ENABLED=true")
    return listen_addr


def _network_prefer() -> int:
    prefer = int(MTPROTO_NETWORK_PREFER)
    if prefer not in {4, 6}:
        raise ValueError("MTPROTO_NETWORK_PREFER must be either 4 or 6")
    return prefer


def _log_level() -> str:
    level = MTPROTO_LOG_LEVEL.strip().lower()
    if level not in {"debug", "verbose", "normal", "silent"}:
        raise ValueError(
            "MTPROTO_LOG_LEVEL must be one of: debug, verbose, normal, silent"
        )
    return level


def _positive_timeout(value: int, name: str) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


def _dummy_secret() -> str:
    return sha256(b"marzban-node-mtproto-dummy").hexdigest()[:32]


def _validate_user_secret(secret: str) -> None:
    if len(secret) != 32 or any(ch not in "0123456789abcdef" for ch in secret):
        raise ValueError("MTProto user secret must be a 32-character lowercase hex string")


def render_mtproto_config(users: list[dict[str, str]]) -> str:
    if not mtproto_enabled():
        raise ValueError("MTProto is disabled on this node")

    mode = _secret_mode()
    domain = _runtime_domain()
    listen_addr_ipv4 = _listen_addr_ipv4()
    network_prefer = _network_prefer()
    log_level = _log_level()
    client_handshake_timeout = _positive_timeout(
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT,
        "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT",
    )
    tg_connect_timeout = _positive_timeout(
        MTPROTO_TG_CONNECT_TIMEOUT,
        "MTPROTO_TG_CONNECT_TIMEOUT",
    )
    client_keepalive_timeout = _positive_timeout(
        MTPROTO_CLIENT_KEEPALIVE_TIMEOUT,
        "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT",
    )
    client_ack_timeout = _positive_timeout(
        MTPROTO_CLIENT_ACK_TIMEOUT,
        "MTPROTO_CLIENT_ACK_TIMEOUT",
    )
    lines = [
        "[general]",
        f"use_middle_proxy = {_bool_toml(MTPROTO_USE_MIDDLE_PROXY)}",
        f"log_level = {_quoted_toml(log_level)}",
        "",
        "[general.modes]",
        "classic = false",
        f"secure = {'true' if mode == 'dd' else 'false'}",
        f"tls = {'true' if mode == 'ee' else 'false'}",
        "",
        "[general.links]",
        f'show = {_quoted_toml("*") if MTPROTO_SHOW_LINKS else "[]"}',
        f"public_host = {_quoted_toml(domain)}",
        f"public_port = {MTPROTO_PORT}",
        "",
        "[network]",
        "ipv4 = true",
        f"ipv6 = {_bool_toml(MTPROTO_IPV6_ENABLED)}",
        f"prefer = {network_prefer}",
        "",
        "[server]",
        f"port = {MTPROTO_PORT}",
        f'listen_addr_ipv4 = {_quoted_toml(listen_addr_ipv4)}',
    ]

    if mode == "ee":
        lines.extend(
            [
                "",
                "[censorship]",
                f"tls_domain = {_quoted_toml(_tls_domain())}",
            ]
        )

    lines.extend(
        [
            "",
            "[timeouts]",
            f"client_handshake = {client_handshake_timeout}",
            f"tg_connect = {tg_connect_timeout}",
            f"client_keepalive = {client_keepalive_timeout}",
            f"client_ack = {client_ack_timeout}",
            "",
            "[access.users]",
        ]
    )
    lines.append(f'"__disabled__" = {_quoted_toml(_dummy_secret())}')

    for user in users:
        secret = user["secret"].strip()
        _validate_user_secret(secret)
        lines.append(f'{_quoted_toml(user["username"])} = {_quoted_toml(secret)}')

    lines.append("")
    return "\n".join(lines)


def get_mtproto_status(configured_users: int | None = None) -> dict:
    path = Path(MTPROTO_CONFIG_PATH)
    mode = _secret_mode() if mtproto_enabled() else MTPROTO_MODE
    listen_addr_ipv4 = (
        _listen_addr_ipv4() if mtproto_enabled() else MTPROTO_LISTEN_ADDR_IPV4.strip()
    )
    network_prefer = _network_prefer()
    log_level = _log_level()
    reload_interval = _positive_timeout(
        MTPROTO_RELOAD_INTERVAL,
        "MTPROTO_RELOAD_INTERVAL",
    )
    client_handshake_timeout = _positive_timeout(
        MTPROTO_CLIENT_HANDSHAKE_TIMEOUT,
        "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT",
    )
    tg_connect_timeout = _positive_timeout(
        MTPROTO_TG_CONNECT_TIMEOUT,
        "MTPROTO_TG_CONNECT_TIMEOUT",
    )
    client_keepalive_timeout = _positive_timeout(
        MTPROTO_CLIENT_KEEPALIVE_TIMEOUT,
        "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT",
    )
    client_ack_timeout = _positive_timeout(
        MTPROTO_CLIENT_ACK_TIMEOUT,
        "MTPROTO_CLIENT_ACK_TIMEOUT",
    )
    return {
        "enabled": mtproto_enabled(),
        "domain": MTPROTO_DOMAIN.strip(),
        "port": MTPROTO_PORT,
        "mode": mode,
        "tls_domain": MTPROTO_TLS_DOMAIN.strip(),
        "use_middle_proxy": MTPROTO_USE_MIDDLE_PROXY,
        "show_links": MTPROTO_SHOW_LINKS,
        "log_level": log_level,
        "rust_log": MTPROTO_RUST_LOG,
        "listen_addr_ipv4": listen_addr_ipv4,
        "ipv6_enabled": MTPROTO_IPV6_ENABLED,
        "network_prefer": network_prefer,
        "reload_interval": reload_interval,
        "client_handshake_timeout": client_handshake_timeout,
        "tg_connect_timeout": tg_connect_timeout,
        "client_keepalive_timeout": client_keepalive_timeout,
        "client_ack_timeout": client_ack_timeout,
        "config_path": str(path),
        "config_exists": path.exists(),
        "configured_users": configured_users,
    }


def apply_mtproto_users(users: list[dict[str, str]]) -> dict:
    path = Path(MTPROTO_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    config_text = render_mtproto_config(users)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(config_text, encoding="utf-8")
    tmp_path.replace(path)

    logger.info("MTProto config synced to %s", path)
    return get_mtproto_status(configured_users=len(users))
