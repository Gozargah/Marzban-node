#!/usr/bin/env bash
# setup-hysteria-node.sh — fully automated Hysteria2 sidecar setup for Marzban-node.
#
# Usage (one command, no pre-config needed):
#   bash <(curl -fsSL https://raw.githubusercontent.com/MaximPyatin/Marzban-node/dev/setup-hysteria-node.sh)
#
# The script asks 2 questions (main Marzban URL + hook token),
# then writes hysteria.yaml, docker-compose.override.yml and starts everything.

set -euo pipefail

# ── auto-detect node directory ────────────────────────────────────────────────

CANDIDATE_DIRS=(
    "/opt/marzban-node"
    "/opt/Marzban-node"
    "/root/Marzban-node"
    "/root/marzban-node"
    "$(pwd)"
)

NODE_COMPOSE_DIR=""
for d in "${CANDIDATE_DIRS[@]}"; do
    if [ -f "$d/docker-compose.yml" ] || [ -f "$d/docker-compose.yaml" ]; then
        NODE_COMPOSE_DIR="$d"
        break
    fi
done

# If no existing docker-compose.yml found, fall back to the first existing dir
if [ -z "$NODE_COMPOSE_DIR" ]; then
    for d in "${CANDIDATE_DIRS[@]}"; do
        if [ -d "$d" ]; then
            NODE_COMPOSE_DIR="$d"
            break
        fi
    done
fi

[ -z "$NODE_COMPOSE_DIR" ] && NODE_COMPOSE_DIR="/opt/marzban-node"

NODE_DATA_DIR="${NODE_DATA_DIR:-/var/lib/marzban-node}"
ENV_FILE="${NODE_COMPOSE_DIR}/.env"
HYSTERIA_YAML="${NODE_DATA_DIR}/hysteria.yaml"
OVERRIDE_FILE="${NODE_COMPOSE_DIR}/docker-compose.override.yml"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[setup-hysteria-node] $*"; }
warn() { echo "[setup-hysteria-node] WARN: $*"; }
err()  { echo "[setup-hysteria-node] ERROR: $*" >&2; exit 1; }

env_get() {
    local key="$1" default="${2:-}"
    if [ -f "$ENV_FILE" ]; then
        # handle both KEY=VALUE and KEY = VALUE
        local val
        val=$(grep -E "^${key}\s*=" "$ENV_FILE" 2>/dev/null | tail -1 \
              | sed -E "s/^${key}\s*=\s*//" | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)
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

generate_secret() {
    python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null \
        || openssl rand -hex 32 2>/dev/null \
        || cat /dev/urandom | tr -dc 'a-f0-9' | fold -w 64 | head -n 1
}

# ── banner ────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  Marzban-node: Hysteria2 sidecar setup"
echo "  Node dir : $NODE_COMPOSE_DIR"
echo "  Data dir : $NODE_DATA_DIR"
echo "=========================================="
echo ""

# ── resolve required values ───────────────────────────────────────────────────

MARZBAN_URL="${HYSTERIA2_MARZBAN_URL:-$(env_get HYSTERIA2_MARZBAN_URL)}"
if [ -z "$MARZBAN_URL" ]; then
    # /dev/tty is required when script is piped via bash <(curl ...) — stdin is the pipe, not the terminal
    read -rp "  Main Marzban URL (e.g. https://config.the-tech.studio): " MARZBAN_URL </dev/tty
fi
MARZBAN_URL="${MARZBAN_URL%/}"
[ -z "$MARZBAN_URL" ] && err "HYSTERIA2_MARZBAN_URL is required. Pass it as env var: HYSTERIA2_MARZBAN_URL=https://... bash <(curl ...)"

HOOK_TOKEN="${HYSTERIA2_HOOK_TOKEN:-$(env_get HYSTERIA2_HOOK_TOKEN)}"
if [ -z "$HOOK_TOKEN" ]; then
    read -rp "  HYSTERIA2_HOOK_TOKEN from main Marzban .env: " HOOK_TOKEN </dev/tty
fi
[ -z "$HOOK_TOKEN" ] && err "HYSTERIA2_HOOK_TOKEN is required. Pass it as env var: HYSTERIA2_HOOK_TOKEN=... bash <(curl ...)"

HYSTERIA_PORT="$(env_get HYSTERIA2_PORT 2083)"

# Generate secrets if not present
TRAFFIC_SECRET="$(env_get HYSTERIA2_TRAFFIC_SECRET)"
if [ -z "$TRAFFIC_SECRET" ]; then
    TRAFFIC_SECRET="$(generate_secret)"
    log "Generated HYSTERIA2_TRAFFIC_SECRET"
fi

TRAFFIC_LISTEN="$(env_get HYSTERIA2_TRAFFIC_LISTEN "127.0.0.1:9999")"
UP_MBPS="$(env_get HYSTERIA2_UP_MBPS 500)"
DOWN_MBPS="$(env_get HYSTERIA2_DOWN_MBPS 500)"

# TLS: prefer existing certs; fall back to node self-signed
CERT_FILE="${NODE_DATA_DIR}/ssl_cert.pem"
KEY_FILE="${NODE_DATA_DIR}/ssl_key.pem"

# ── ensure node cert exists (start node briefly if needed) ───────────────────

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    warn "Node SSL certs not found. Starting marzban-node to generate them..."
    if [ -f "${NODE_COMPOSE_DIR}/docker-compose.yml" ] || [ -f "${NODE_COMPOSE_DIR}/docker-compose.yaml" ]; then
        (cd "$NODE_COMPOSE_DIR" && docker compose up -d marzban-node) || true
        log "Waiting up to 15 s for cert generation..."
        for i in $(seq 1 15); do
            sleep 1
            [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ] && break
        done
    fi

    if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
        warn "Certs still missing at $CERT_FILE — hysteriad will fail until the node generates them."
        warn "Re-run this script after the node is started at least once."
    fi
fi

# ── write .env ────────────────────────────────────────────────────────────────

log "Updating ${ENV_FILE}..."
mkdir -p "$NODE_DATA_DIR"

env_set HYSTERIA2_ENABLED        true
env_set HYSTERIA2_PORT           "$HYSTERIA_PORT"
env_set HYSTERIA2_MARZBAN_URL    "$MARZBAN_URL"
env_set HYSTERIA2_HOOK_TOKEN     "$HOOK_TOKEN"
env_set HYSTERIA2_TRAFFIC_SECRET "$TRAFFIC_SECRET"
env_set HYSTERIA2_TRAFFIC_LISTEN "$TRAFFIC_LISTEN"
env_set HYSTERIA2_UP_MBPS        "$UP_MBPS"
env_set HYSTERIA2_DOWN_MBPS      "$DOWN_MBPS"

# ── write hysteria.yaml ───────────────────────────────────────────────────────

if [ -f "$HYSTERIA_YAML" ]; then
    cp "$HYSTERIA_YAML" "${HYSTERIA_YAML}.bak"
    log "Backed up existing hysteria.yaml → hysteria.yaml.bak"
fi

log "Writing ${HYSTERIA_YAML}..."
cat > "$HYSTERIA_YAML" << YAML
# Auto-generated by setup-hysteria-node.sh — do not edit manually.
# Re-run the script to regenerate.

listen: ":${HYSTERIA_PORT}"

tls:
  cert: /var/lib/marzban-node/ssl_cert.pem
  key:  /var/lib/marzban-node/ssl_key.pem

auth:
  type: http
  http:
    url: ${MARZBAN_URL}/api/hysteria/auth?token=${HOOK_TOKEN}
    insecure: true

bandwidth:
  up:   ${UP_MBPS} mbps
  down: ${DOWN_MBPS} mbps

trafficStats:
  listen: ${TRAFFIC_LISTEN}
  secret: ${TRAFFIC_SECRET}

masquerade:
  type: proxy
  proxy:
    url: https://news.ycombinator.com
    rewriteHost: true
YAML

log "hysteria.yaml written."

# ── write docker-compose.override.yml ────────────────────────────────────────
# Using override avoids touching the existing docker-compose.yml.
# Docker Compose merges them automatically.

log "Writing ${OVERRIDE_FILE}..."
cat > "$OVERRIDE_FILE" << 'COMPOSE'
# Auto-generated by setup-hysteria-node.sh
# Adds the hysteria2 sidecar to any existing docker-compose.yml.

services:
  hysteria2:
    image: tobyxdd/hysteria:latest
    restart: always
    network_mode: host
    volumes:
      - /var/lib/marzban-node:/var/lib/marzban-node:ro
      - /var/lib/marzban-node/hysteria.yaml:/etc/hysteria/config.yaml:ro
    command: server
COMPOSE

log "docker-compose.override.yml written."

# ── pull hysteria image ───────────────────────────────────────────────────────

log "Pulling hysteria image..."
(cd "$NODE_COMPOSE_DIR" && docker compose pull hysteria2) || \
    docker pull tobyxdd/hysteria:latest || true

# ── start everything ──────────────────────────────────────────────────────────

log "Starting all services..."
cd "$NODE_COMPOSE_DIR"
docker compose up -d

# ── verify ────────────────────────────────────────────────────────────────────

echo ""
log "Services status:"
docker compose ps

echo ""
log "Waiting 5 s for hysteriad to initialize..."
sleep 5

HYSTERIA_CONTAINER=$(docker compose ps -q hysteria2 2>/dev/null || true)
if [ -n "$HYSTERIA_CONTAINER" ]; then
    log "hysteria2 container logs (last 20 lines):"
    docker compose logs --tail=20 hysteria2 2>/dev/null || true
else
    warn "hysteria2 container not found — check docker compose ps"
fi

echo ""
log "Testing auth endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${MARZBAN_URL}/api/hysteria/auth?token=${HOOK_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"addr":"127.0.0.1:1234","auth":"probe_test","id":"probe"}' \
    --connect-timeout 5 --max-time 10 -k 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    log "Auth endpoint reachable (HTTP ${HTTP_CODE}) ✓"
    if [ "$HTTP_CODE" = "403" ]; then
        warn "  HTTP 403 — check that HYSTERIA2_HOOK_TOKEN matches the one in main Marzban .env"
    fi
else
    warn "Auth endpoint returned HTTP ${HTTP_CODE} — verify MARZBAN_URL and network connectivity"
fi

echo ""
log "=========================================="
log "  Done!"
log ""
log "  Hysteria2 is listening on :${HYSTERIA_PORT}"
log "  Auth  → ${MARZBAN_URL}"
log "  Stats → ${TRAFFIC_LISTEN}"
log ""
log "  To verify a user password:"
log "    curl -sk -X POST '${MARZBAN_URL}/api/hysteria/auth?token=${HOOK_TOKEN}' \\"
log "         -H 'Content-Type: application/json' \\"
log "         -d '{\"addr\":\"127.0.0.1:1234\",\"auth\":\"USER_HY2_PASSWORD\",\"id\":\"test\"}'"
log "=========================================="
