#!/usr/bin/env bash
set -euo pipefail

CANDIDATE_DIRS=(
  "/opt/marzban-node"
  "/opt/Marzban-node"
  "/root/Marzban-node"
  "/root/marzban-node"
  "$(pwd)"
)

NODE_COMPOSE_DIR="${NODE_COMPOSE_DIR:-}"
if [ -z "$NODE_COMPOSE_DIR" ]; then
  for d in "${CANDIDATE_DIRS[@]}"; do
    if [ -f "$d/docker-compose.yml" ] || [ -f "$d/docker-compose.yaml" ]; then
      NODE_COMPOSE_DIR="$d"
      break
    fi
  done
fi

[ -z "$NODE_COMPOSE_DIR" ] && {
  echo "ERROR: Could not find marzban-node docker-compose.yml"
  exit 1
}

NODE_DATA_DIR="${NODE_DATA_DIR:-/var/lib/marzban-node}"
ENV_FILE="${NODE_COMPOSE_DIR}/.env"
OVERRIDE_FILE="${NODE_COMPOSE_DIR}/docker-compose.override.yml"
MTPROTO_CONFIG_PATH_DEFAULT="${NODE_DATA_DIR}/mtproto/telemt.toml"

log() { echo "[mtproto-setup] $*"; }
err() { echo "[mtproto-setup] ERROR: $*" >&2; exit 1; }

env_get() {
  local key="$1" default="${2:-}"
  if [ -f "$ENV_FILE" ]; then
    local val
    val=$(sed -n -E "s/^${key}\s*=\s*//p" "$ENV_FILE" | tail -1 | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)
    echo "${val:-$default}"
  else
    echo "$default"
  fi
}

env_set() {
  local key="$1" value="$2"
  mkdir -p "$(dirname "$ENV_FILE")"
  touch "$ENV_FILE"
  if grep -qE "^${key}\s*=" "$ENV_FILE" 2>/dev/null; then
    sed -i -E "s|^${key}\s*=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

ask() {
  local var="$1" prompt="$2" default="${3:-}"
  local current="${!var:-}"
  [ -n "$current" ] && return
  current="$(env_get "$var" "$default")"
  if [ -n "$current" ]; then
    printf -v "$var" '%s' "$current"
    return
  fi
  local answer
  read -rp "  $prompt: " answer </dev/tty
  printf -v "$var" '%s' "$answer"
}

echo ""
echo "Node dir : $NODE_COMPOSE_DIR"
echo "Data dir : $NODE_DATA_DIR"
echo ""

ask MTPROTO_DOMAIN "MTProto node domain (e.g. tg.example.com)"
[ -z "${MTPROTO_DOMAIN:-}" ] && err "MTPROTO_DOMAIN is required"

ask MTPROTO_PORT "MTProto port" "1443"
ask MTPROTO_MODE "MTProto mode (dd or ee)" "dd"

case "$MTPROTO_MODE" in
  dd|ee) ;;
  *) err "MTPROTO_MODE must be dd or ee" ;;
esac

MTPROTO_TLS_DOMAIN="${MTPROTO_TLS_DOMAIN:-$(env_get MTPROTO_TLS_DOMAIN)}"
if [ "$MTPROTO_MODE" = "ee" ] && [ -z "$MTPROTO_TLS_DOMAIN" ]; then
  read -rp "  TLS domain for ee mode: " MTPROTO_TLS_DOMAIN </dev/tty
fi

if [ "$MTPROTO_MODE" = "ee" ] && [ -z "$MTPROTO_TLS_DOMAIN" ]; then
  err "MTPROTO_TLS_DOMAIN is required when MTPROTO_MODE=ee"
fi

MTPROTO_USE_MIDDLE_PROXY="${MTPROTO_USE_MIDDLE_PROXY:-$(env_get MTPROTO_USE_MIDDLE_PROXY true)}"
MTPROTO_LISTEN_ADDR_IPV4="${MTPROTO_LISTEN_ADDR_IPV4:-$(env_get MTPROTO_LISTEN_ADDR_IPV4 0.0.0.0)}"
MTPROTO_IPV6_ENABLED="${MTPROTO_IPV6_ENABLED:-$(env_get MTPROTO_IPV6_ENABLED false)}"
MTPROTO_NETWORK_PREFER="${MTPROTO_NETWORK_PREFER:-$(env_get MTPROTO_NETWORK_PREFER 4)}"
MTPROTO_SHOW_LINKS="${MTPROTO_SHOW_LINKS:-$(env_get MTPROTO_SHOW_LINKS false)}"
MTPROTO_LOG_LEVEL="${MTPROTO_LOG_LEVEL:-$(env_get MTPROTO_LOG_LEVEL normal)}"
MTPROTO_RUST_LOG="${MTPROTO_RUST_LOG:-$(env_get MTPROTO_RUST_LOG info,telemt::links=warn)}"
MTPROTO_RELOAD_INTERVAL="${MTPROTO_RELOAD_INTERVAL:-$(env_get MTPROTO_RELOAD_INTERVAL 5)}"
MTPROTO_PROCESS_RESTART_DELAY_MS="${MTPROTO_PROCESS_RESTART_DELAY_MS:-$(env_get MTPROTO_PROCESS_RESTART_DELAY_MS 1000)}"
MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS="${MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS:-$(env_get MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS 3)}"
MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS="${MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS:-$(env_get MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS 250)}"
MTPROTO_UPSTREAM_CONNECT_BUDGET_MS="${MTPROTO_UPSTREAM_CONNECT_BUDGET_MS:-$(env_get MTPROTO_UPSTREAM_CONNECT_BUDGET_MS 25000)}"
MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD="${MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD:-$(env_get MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD 3)}"
MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS="${MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS:-$(env_get MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS false)}"
# Keep defaults resilient: tg_connect is a max wait budget, not a fixed delay.
MTPROTO_CLIENT_HANDSHAKE_TIMEOUT="${MTPROTO_CLIENT_HANDSHAKE_TIMEOUT:-$(env_get MTPROTO_CLIENT_HANDSHAKE_TIMEOUT 25)}"
MTPROTO_TG_CONNECT_TIMEOUT="${MTPROTO_TG_CONNECT_TIMEOUT:-$(env_get MTPROTO_TG_CONNECT_TIMEOUT 20)}"
MTPROTO_CLIENT_KEEPALIVE_TIMEOUT="${MTPROTO_CLIENT_KEEPALIVE_TIMEOUT:-$(env_get MTPROTO_CLIENT_KEEPALIVE_TIMEOUT 60)}"
MTPROTO_CLIENT_ACK_TIMEOUT="${MTPROTO_CLIENT_ACK_TIMEOUT:-$(env_get MTPROTO_CLIENT_ACK_TIMEOUT 300)}"

case "$MTPROTO_USE_MIDDLE_PROXY" in
  true|false) ;;
  *) err "MTPROTO_USE_MIDDLE_PROXY must be true or false" ;;
esac

case "$MTPROTO_IPV6_ENABLED" in
  true|false) ;;
  *) err "MTPROTO_IPV6_ENABLED must be true or false" ;;
esac

case "$MTPROTO_SHOW_LINKS" in
  true|false) ;;
  *) err "MTPROTO_SHOW_LINKS must be true or false" ;;
esac

case "$MTPROTO_NETWORK_PREFER" in
  4|6) ;;
  *) err "MTPROTO_NETWORK_PREFER must be 4 or 6" ;;
esac

case "$MTPROTO_LOG_LEVEL" in
  debug|verbose|normal|silent) ;;
  *) err "MTPROTO_LOG_LEVEL must be debug, verbose, normal or silent" ;;
esac

case "$MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS" in
  true|false) ;;
  *) err "MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS must be true or false" ;;
esac

[[ "$MTPROTO_CLIENT_HANDSHAKE_TIMEOUT" =~ ^[0-9]+$ ]] || err "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT must be a positive integer"
[[ "$MTPROTO_TG_CONNECT_TIMEOUT" =~ ^[0-9]+$ ]] || err "MTPROTO_TG_CONNECT_TIMEOUT must be a positive integer"
[[ "$MTPROTO_RELOAD_INTERVAL" =~ ^[0-9]+$ ]] || err "MTPROTO_RELOAD_INTERVAL must be a positive integer"
[[ "$MTPROTO_PROCESS_RESTART_DELAY_MS" =~ ^[0-9]+$ ]] || err "MTPROTO_PROCESS_RESTART_DELAY_MS must be a positive integer"
[[ "$MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS" =~ ^[0-9]+$ ]] || err "MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS must be a positive integer"
[[ "$MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS" =~ ^[0-9]+$ ]] || err "MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS must be a positive integer"
[[ "$MTPROTO_UPSTREAM_CONNECT_BUDGET_MS" =~ ^[0-9]+$ ]] || err "MTPROTO_UPSTREAM_CONNECT_BUDGET_MS must be a positive integer"
[[ "$MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD" =~ ^[0-9]+$ ]] || err "MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD must be a positive integer"
[[ "$MTPROTO_CLIENT_KEEPALIVE_TIMEOUT" =~ ^[0-9]+$ ]] || err "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT must be a positive integer"
[[ "$MTPROTO_CLIENT_ACK_TIMEOUT" =~ ^[0-9]+$ ]] || err "MTPROTO_CLIENT_ACK_TIMEOUT must be a positive integer"
[ "$MTPROTO_CLIENT_HANDSHAKE_TIMEOUT" -gt 0 ] || err "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT must be greater than 0"
[ "$MTPROTO_TG_CONNECT_TIMEOUT" -gt 0 ] || err "MTPROTO_TG_CONNECT_TIMEOUT must be greater than 0"
[ "$MTPROTO_RELOAD_INTERVAL" -gt 0 ] || err "MTPROTO_RELOAD_INTERVAL must be greater than 0"
[ "$MTPROTO_PROCESS_RESTART_DELAY_MS" -gt 0 ] || err "MTPROTO_PROCESS_RESTART_DELAY_MS must be greater than 0"
[ "$MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS" -gt 0 ] || err "MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS must be greater than 0"
[ "$MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS" -gt 0 ] || err "MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS must be greater than 0"
[ "$MTPROTO_UPSTREAM_CONNECT_BUDGET_MS" -gt 0 ] || err "MTPROTO_UPSTREAM_CONNECT_BUDGET_MS must be greater than 0"
[ "$MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD" -gt 0 ] || err "MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD must be greater than 0"
[ "$MTPROTO_CLIENT_KEEPALIVE_TIMEOUT" -gt 0 ] || err "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT must be greater than 0"
[ "$MTPROTO_CLIENT_ACK_TIMEOUT" -gt 0 ] || err "MTPROTO_CLIENT_ACK_TIMEOUT must be greater than 0"
[ "$MTPROTO_CLIENT_HANDSHAKE_TIMEOUT" -ge "$MTPROTO_TG_CONNECT_TIMEOUT" ] || err "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT must be greater than or equal to MTPROTO_TG_CONNECT_TIMEOUT"
[ "$MTPROTO_UPSTREAM_CONNECT_BUDGET_MS" -ge $((MTPROTO_TG_CONNECT_TIMEOUT * 1000)) ] || err "MTPROTO_UPSTREAM_CONNECT_BUDGET_MS must be greater than or equal to MTPROTO_TG_CONNECT_TIMEOUT * 1000"
[ -n "$MTPROTO_LISTEN_ADDR_IPV4" ] || err "MTPROTO_LISTEN_ADDR_IPV4 is required"
[ -n "$MTPROTO_RUST_LOG" ] || err "MTPROTO_RUST_LOG is required"

mkdir -p "${NODE_DATA_DIR}/mtproto"

log "Updating ${ENV_FILE}..."
env_set MTPROTO_ENABLED true
env_set MTPROTO_DOMAIN "$MTPROTO_DOMAIN"
env_set MTPROTO_PORT "$MTPROTO_PORT"
env_set MTPROTO_MODE "$MTPROTO_MODE"
env_set MTPROTO_TLS_DOMAIN "$MTPROTO_TLS_DOMAIN"
env_set MTPROTO_USE_MIDDLE_PROXY "$MTPROTO_USE_MIDDLE_PROXY"
env_set MTPROTO_LISTEN_ADDR_IPV4 "$MTPROTO_LISTEN_ADDR_IPV4"
env_set MTPROTO_IPV6_ENABLED "$MTPROTO_IPV6_ENABLED"
env_set MTPROTO_NETWORK_PREFER "$MTPROTO_NETWORK_PREFER"
env_set MTPROTO_SHOW_LINKS "$MTPROTO_SHOW_LINKS"
env_set MTPROTO_LOG_LEVEL "$MTPROTO_LOG_LEVEL"
env_set MTPROTO_RUST_LOG "$MTPROTO_RUST_LOG"
env_set MTPROTO_RELOAD_INTERVAL "$MTPROTO_RELOAD_INTERVAL"
env_set MTPROTO_PROCESS_RESTART_DELAY_MS "$MTPROTO_PROCESS_RESTART_DELAY_MS"
env_set MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS "$MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS"
env_set MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS "$MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS"
env_set MTPROTO_UPSTREAM_CONNECT_BUDGET_MS "$MTPROTO_UPSTREAM_CONNECT_BUDGET_MS"
env_set MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD "$MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD"
env_set MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS "$MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS"
env_set MTPROTO_CLIENT_HANDSHAKE_TIMEOUT "$MTPROTO_CLIENT_HANDSHAKE_TIMEOUT"
env_set MTPROTO_TG_CONNECT_TIMEOUT "$MTPROTO_TG_CONNECT_TIMEOUT"
env_set MTPROTO_CLIENT_KEEPALIVE_TIMEOUT "$MTPROTO_CLIENT_KEEPALIVE_TIMEOUT"
env_set MTPROTO_CLIENT_ACK_TIMEOUT "$MTPROTO_CLIENT_ACK_TIMEOUT"
env_set MTPROTO_CONFIG_PATH "$MTPROTO_CONFIG_PATH_DEFAULT"

log "Writing ${OVERRIDE_FILE}..."
cat > "$OVERRIDE_FILE" <<COMPOSE
services:
  mtproto:
    build:
      context: .
      dockerfile: docker/mtproto/Dockerfile
    restart: always
    env_file: .env
    network_mode: host
    cap_add:
      - NET_BIND_SERVICE
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - ${NODE_DATA_DIR}:${NODE_DATA_DIR}
COMPOSE

log "Starting mtproto sidecar..."
cd "$NODE_COMPOSE_DIR"
docker compose up -d --build mtproto

echo ""
log "Container status:"
docker compose ps mtproto || true

echo ""
log "Recent mtproto logs:"
docker compose logs --tail=20 mtproto || true

echo ""
echo "Next:"
echo "1. Set on main Marzban host:"
echo "   MTPROTO_NODE_NAME=<this node name in panel>"
echo "   MTPROTO_PUBLIC_HOST=${MTPROTO_DOMAIN}"
echo "   MTPROTO_PUBLIC_PORT=${MTPROTO_PORT}"
echo "   MTPROTO_SECRET_MODE=${MTPROTO_MODE}"
if [ "$MTPROTO_MODE" = "ee" ]; then
  echo "   MTPROTO_TLS_DOMAIN=${MTPROTO_TLS_DOMAIN}"
fi
echo "2. Restart main Marzban so it syncs MTProto users to this node."
echo "3. Node telemt runtime defaults written:"
echo "   Note: MTPROTO_TG_CONNECT_TIMEOUT is the maximum wait for node -> Telegram, not a fixed delay for every client."
echo "   MTPROTO_USE_MIDDLE_PROXY=${MTPROTO_USE_MIDDLE_PROXY}"
echo "   MTPROTO_LISTEN_ADDR_IPV4=${MTPROTO_LISTEN_ADDR_IPV4}"
echo "   MTPROTO_IPV6_ENABLED=${MTPROTO_IPV6_ENABLED}"
echo "   MTPROTO_NETWORK_PREFER=${MTPROTO_NETWORK_PREFER}"
echo "   MTPROTO_SHOW_LINKS=${MTPROTO_SHOW_LINKS}"
echo "   MTPROTO_LOG_LEVEL=${MTPROTO_LOG_LEVEL}"
echo "   MTPROTO_RUST_LOG=${MTPROTO_RUST_LOG}"
echo "   MTPROTO_RELOAD_INTERVAL=${MTPROTO_RELOAD_INTERVAL}"
echo "   MTPROTO_PROCESS_RESTART_DELAY_MS=${MTPROTO_PROCESS_RESTART_DELAY_MS}"
echo "   MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS=${MTPROTO_UPSTREAM_CONNECT_RETRY_ATTEMPTS}"
echo "   MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS=${MTPROTO_UPSTREAM_CONNECT_RETRY_BACKOFF_MS}"
echo "   MTPROTO_UPSTREAM_CONNECT_BUDGET_MS=${MTPROTO_UPSTREAM_CONNECT_BUDGET_MS}"
echo "   MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD=${MTPROTO_UPSTREAM_UNHEALTHY_FAIL_THRESHOLD}"
echo "   MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS=${MTPROTO_UPSTREAM_CONNECT_FAILFAST_HARD_ERRORS}"
echo "   MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=${MTPROTO_CLIENT_HANDSHAKE_TIMEOUT}"
echo "   MTPROTO_TG_CONNECT_TIMEOUT=${MTPROTO_TG_CONNECT_TIMEOUT}"
echo "   MTPROTO_CLIENT_KEEPALIVE_TIMEOUT=${MTPROTO_CLIENT_KEEPALIVE_TIMEOUT}"
echo "   MTPROTO_CLIENT_ACK_TIMEOUT=${MTPROTO_CLIENT_ACK_TIMEOUT}"