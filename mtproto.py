from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from config import (
    MTPROTO_CONFIG_PATH,
    MTPROTO_DOMAIN,
    MTPROTO_ENABLED,
    MTPROTO_MODE,
    MTPROTO_PORT,
    MTPROTO_TLS_DOMAIN,
)
from logger import logger


def mtproto_enabled() -> bool:
    return bool(MTPROTO_ENABLED)


def _quoted_toml(value: str) -> str:
    return json.dumps(value)


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
    lines = [
        "[general]",
        "use_middle_proxy = false",
        "",
        "[general.modes]",
        "classic = false",
        f"secure = {'true' if mode == 'dd' else 'false'}",
        f"tls = {'true' if mode == 'ee' else 'false'}",
        "",
        "[general.links]",
        f"public_host = {_quoted_toml(domain)}",
        f"public_port = {MTPROTO_PORT}",
        "",
        "[server]",
        f"port = {MTPROTO_PORT}",
    ]

    if mode == "ee":
        lines.extend(
            [
                "",
                "[censorship]",
                f"tls_domain = {_quoted_toml(_tls_domain())}",
            ]
        )

    lines.extend(["", "[access.users]"])
    lines.append(f'"__disabled__" = {_quoted_toml(_dummy_secret())}')

    for user in users:
        secret = user["secret"].strip()
        _validate_user_secret(secret)
        lines.append(f'{_quoted_toml(user["username"])} = {_quoted_toml(secret)}')

    lines.append("")
    return "\n".join(lines)


def get_mtproto_status(configured_users: int | None = None) -> dict:
    path = Path(MTPROTO_CONFIG_PATH)
    return {
        "enabled": mtproto_enabled(),
        "domain": MTPROTO_DOMAIN.strip(),
        "port": MTPROTO_PORT,
        "mode": MTPROTO_MODE,
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
