#!/bin/sh
set -eu

CONFIG_PATH="${MTPROTO_CONFIG_PATH:-/var/lib/marzban-node/mtproto/telemt.toml}"
POLL_INTERVAL="${MTPROTO_RELOAD_INTERVAL:-5}"
RUST_LOG_FILTER="${MTPROTO_RUST_LOG:-info,telemt::links=warn}"
RESTART_DELAY_MS="${MTPROTO_PROCESS_RESTART_DELAY_MS:-1000}"

child_pid=""
started_once="0"

cleanup() {
  if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
    kill "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup INT TERM

start_proxy() {
  RUST_LOG="$RUST_LOG_FILTER" /usr/local/bin/telemt "$CONFIG_PATH" &
  child_pid="$!"
}

stop_proxy() {
  if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
    kill "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  child_pid=""
}

sleep_ms() {
  ms="$1"
  awk "BEGIN { printf \"%.3f\", ${ms}/1000 }" | xargs sleep
}

while true; do
  if [ ! -f "$CONFIG_PATH" ]; then
    sleep "$POLL_INTERVAL"
    continue
  fi

  if [ -z "$child_pid" ] || ! kill -0 "$child_pid" 2>/dev/null; then
    if [ "$started_once" = "1" ]; then
      sleep_ms "$RESTART_DELAY_MS"
    fi
    start_proxy
    started_once="1"
  fi

  sleep "$POLL_INTERVAL"
done
