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

mkdir -p "${NODE_DATA_DIR}/mtproto"

log "Updating ${ENV_FILE}..."
env_set MTPROTO_ENABLED true
env_set MTPROTO_DOMAIN "$MTPROTO_DOMAIN"
env_set MTPROTO_PORT "$MTPROTO_PORT"
env_set MTPROTO_MODE "$MTPROTO_MODE"
env_set MTPROTO_TLS_DOMAIN "$MTPROTO_TLS_DOMAIN"
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
