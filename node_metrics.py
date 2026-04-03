"""
Background sampler for GET /metrics (Smart DNS load balancing).
Uses psutil for CPU and hysteriad traffic HTTP API for bandwidth / active user proxy.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

import psutil

from config import (
    HYSTERIA2_ENABLED,
    HYSTERIA2_TRAFFIC_LISTEN,
    HYSTERIA2_TRAFFIC_SECRET,
    NODE_METRICS_INTERVAL,
)
from logger import logger

_lock = threading.Lock()
_snapshot: dict = {
    "active_connections": 0,
    "bandwidth_mbps": 0.0,
    "cpu": 0.0,
    "status": "UP",
}
_stop = threading.Event()
_thread: Optional[threading.Thread] = None

# Hysteria sampling
_last_total_bytes: Optional[int] = None
_last_sample_ts: float = 0.0
_traffic_fail_streak = 0
_cpu_initialized = False
_missing_secret_logged = False


def _parse_traffic_listen(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (host, port) from HYSTERIA2_TRAFFIC_LISTEN; host without brackets."""
    s = raw.strip()
    if not s:
        return None, None
    if s.startswith("["):
        end = s.find("]")
        if end < 2:
            return None, None
        inner = s[1:end].strip()
        rest = s[end + 1 :].strip()
        if not rest.startswith(":"):
            return None, None
        port = rest[1:].strip()
        return inner, port
    if ":" not in s:
        return None, None
    host, _, port = s.rpartition(":")
    return host.strip(), port.strip()


def _traffic_stats_http_base() -> Optional[str]:
    """
    Base URL for Hysteria trafficStats HTTP API (no path), e.g. http://127.0.0.1:9999.
    None if secret missing or listen not parseable.
    """
    if not (HYSTERIA2_TRAFFIC_SECRET or "").strip():
        return None
    raw = (HYSTERIA2_TRAFFIC_LISTEN or "").strip()
    host, port = _parse_traffic_listen(raw)
    if not host or not port or not port.isdigit():
        return None
    h0 = host.split("%", 1)[0]
    if host in ("0.0.0.0", "::", "") or h0 == "::":
        bind_host = "127.0.0.1"
    else:
        try:
            ipaddress.IPv6Address(h0)
            return f"http://[{h0}]:{port}"
        except ipaddress.AddressValueError:
            bind_host = host
    return f"http://{bind_host}:{port}"


def _traffic_http_url() -> Optional[str]:
    b = _traffic_stats_http_base()
    return f"{b}/traffic" if b else None


def _fetch_json(url: str) -> Optional[dict]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": (HYSTERIA2_TRAFFIC_SECRET or "").strip()},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body.strip() else {}
            return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logger.debug("node_metrics fetch %s failed: %s", url, e)
        return None


def _sum_traffic_bytes(traffic: dict) -> int:
    total = 0
    for v in traffic.values():
        if not isinstance(v, dict):
            continue
        total += int(v.get("tx", 0) or 0) + int(v.get("rx", 0) or 0)
    return total


def _active_from_online(online: Optional[dict]) -> int:
    """Hysteria GET /online: map client -> number of client instances (devices)."""
    if not online:
        return 0
    n = 0
    for v in online.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            n += v
        else:
            try:
                n += int(v)
            except (TypeError, ValueError):
                pass
    return n


def _merge_active_connections(tmap: dict, online: Optional[dict]) -> int:
    """
    /traffic can be {} while clients are connected (no bytes yet or auth quirk).
    /online reports live sessions — use max(len(traffic), sum(online)).
    """
    a_tr = len(tmap)
    a_on = _active_from_online(online)
    return max(a_tr, a_on)


def _loop(core_started: Callable[[], bool]) -> None:
    global _last_total_bytes, _last_sample_ts, _traffic_fail_streak, _cpu_initialized
    global _missing_secret_logged
    while not _stop.is_set():
        t0 = time.monotonic()
        cpu = 0.0
        try:
            if not _cpu_initialized:
                psutil.cpu_percent(interval=None)
                _cpu_initialized = True
                time.sleep(0.15)
            cpu = float(psutil.cpu_percent(interval=None))
        except Exception as e:
            logger.debug(f"node_metrics cpu: {e}")

        active = 0
        bw_mbps = 0.0
        base = _traffic_stats_http_base()
        traffic_url = f"{base}/traffic" if base else None
        online_url = f"{base}/online" if base else None
        now = time.monotonic()

        if HYSTERIA2_ENABLED and not (HYSTERIA2_TRAFFIC_SECRET or "").strip():
            if not _missing_secret_logged:
                logger.warning(
                    "HYSTERIA2_ENABLED but HYSTERIA2_TRAFFIC_SECRET is empty — "
                    "Smart DNS will show 0 connections / 0 Mbps; set secret to match hysteria.yaml trafficStats.secret"
                )
                _missing_secret_logged = True

        if traffic_url and HYSTERIA2_ENABLED:
            tmap = _fetch_json(traffic_url)
            if tmap is None:
                _traffic_fail_streak += 1
            else:
                _traffic_fail_streak = 0
                omap = _fetch_json(online_url) if online_url else None
                active = _merge_active_connections(tmap, omap)
                total_b = _sum_traffic_bytes(tmap)
                if _last_total_bytes is not None and _last_sample_ts > 0:
                    dt = now - _last_sample_ts
                    if dt > 0.05:
                        delta = total_b - _last_total_bytes
                        if delta < 0:
                            # Marzban panel cleared counters via /traffic?clear=true.
                            # Reset baseline so next interval is accurate.
                            _last_total_bytes = total_b
                            _last_sample_ts = now
                        else:
                            bw_mbps = (delta * 8.0 / dt) / 1_000_000.0
                            _last_total_bytes = total_b
                            _last_sample_ts = now
                else:
                    _last_total_bytes = total_b
                    _last_sample_ts = now
        elif traffic_url and (HYSTERIA2_TRAFFIC_SECRET or "").strip() and not HYSTERIA2_ENABLED:
            tmap = _fetch_json(traffic_url)
            if tmap is not None:
                omap = _fetch_json(online_url) if online_url else None
                active = _merge_active_connections(tmap, omap)
                total_b = _sum_traffic_bytes(tmap)
                now = time.monotonic()
                if _last_total_bytes is not None and _last_sample_ts > 0:
                    dt = now - _last_sample_ts
                    if dt > 0.05:
                        delta = total_b - _last_total_bytes
                        if delta < 0:
                            _last_total_bytes = total_b
                            _last_sample_ts = now
                        else:
                            bw_mbps = (delta * 8.0 / dt) / 1_000_000.0
                            _last_total_bytes = total_b
                            _last_sample_ts = now
                else:
                    _last_total_bytes = total_b
                    _last_sample_ts = now
        else:
            _traffic_fail_streak = 0
            _last_total_bytes = None

        # UP if Xray is running OR Hysteria trafficStats responds (nodes may serve HY2 without Xray started).
        hysteria_cfg = (
            HYSTERIA2_ENABLED
            and (HYSTERIA2_TRAFFIC_SECRET or "").strip()
            and base
        )
        hysteria_stats_ok = bool(hysteria_cfg and _traffic_fail_streak < 3)

        if hysteria_cfg and _traffic_fail_streak >= 3:
            status = "DOWN"
        elif core_started() or hysteria_stats_ok:
            status = "UP"
        else:
            status = "DOWN"

        with _lock:
            _snapshot["active_connections"] = active
            _snapshot["bandwidth_mbps"] = round(bw_mbps, 3)
            _snapshot["cpu"] = round(cpu, 2)
            _snapshot["status"] = status

        elapsed = time.monotonic() - t0
        wait = max(0.1, float(NODE_METRICS_INTERVAL) - elapsed)
        _stop.wait(wait)


def start_metrics_collector(core_started: Callable[[], bool]) -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return

    def runner():
        try:
            _loop(core_started)
        except Exception:
            logger.exception("node_metrics collector crashed")

    _stop.clear()
    _thread = threading.Thread(target=runner, name="node_metrics", daemon=True)
    _thread.start()


def stop_metrics_collector() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5.0)


def get_metrics_snapshot() -> dict:
    with _lock:
        return dict(_snapshot)
