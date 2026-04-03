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
from typing import Callable, Optional, Tuple

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


def _traffic_http_url() -> Optional[str]:
    if not HYSTERIA2_TRAFFIC_SECRET:
        return None
    raw = (HYSTERIA2_TRAFFIC_LISTEN or "").strip()
    host, port = _parse_traffic_listen(raw)
    if not host or not port or not port.isdigit():
        return None
    h0 = host.split("%", 1)[0]
    if host in ("0.0.0.0", "::", "") or h0 == "::":
        return f"http://127.0.0.1:{port}/traffic"
    try:
        ipaddress.IPv6Address(h0)
        return f"http://[{h0}]:{port}/traffic"
    except ipaddress.AddressValueError:
        return f"http://{host}:{port}/traffic"


def _fetch_traffic_map(url: str) -> Optional[dict]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": HYSTERIA2_TRAFFIC_SECRET},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body.strip() else {}
            return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logger.debug(f"node_metrics traffic fetch failed: {e}")
        return None


def _sum_traffic_bytes(traffic: dict) -> int:
    total = 0
    for v in traffic.values():
        if not isinstance(v, dict):
            continue
        total += int(v.get("tx", 0) or 0) + int(v.get("rx", 0) or 0)
    return total


def _loop(core_started: Callable[[], bool]) -> None:
    global _last_total_bytes, _last_sample_ts, _traffic_fail_streak, _cpu_initialized
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
        url = _traffic_http_url()
        now = time.monotonic()

        if url and HYSTERIA2_ENABLED:
            tmap = _fetch_traffic_map(url)
            if tmap is None:
                _traffic_fail_streak += 1
            else:
                _traffic_fail_streak = 0
                active = len(tmap)
                total_b = _sum_traffic_bytes(tmap)
                if _last_total_bytes is not None and _last_sample_ts > 0:
                    dt = now - _last_sample_ts
                    if dt > 0.05:
                        delta = max(0, total_b - _last_total_bytes)
                        bw_mbps = (delta * 8.0 / dt) / 1_000_000.0
                _last_total_bytes = total_b
                _last_sample_ts = now
        elif url and HYSTERIA2_TRAFFIC_SECRET and not HYSTERIA2_ENABLED:
            tmap = _fetch_traffic_map(url)
            if tmap is not None:
                active = len(tmap)
                total_b = _sum_traffic_bytes(tmap)
                now = time.monotonic()
                if _last_total_bytes is not None and _last_sample_ts > 0:
                    dt = now - _last_sample_ts
                    if dt > 0.05:
                        delta = max(0, total_b - _last_total_bytes)
                        bw_mbps = (delta * 8.0 / dt) / 1_000_000.0
                _last_total_bytes = total_b
                _last_sample_ts = now
        else:
            _traffic_fail_streak = 0
            _last_total_bytes = None

        status = "UP"
        if not core_started():
            status = "DOWN"
        elif HYSTERIA2_ENABLED and HYSTERIA2_TRAFFIC_SECRET and url:
            if _traffic_fail_streak >= 3:
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
