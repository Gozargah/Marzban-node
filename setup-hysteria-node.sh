#!/usr/bin/env bash
# setup-hysteria-node.sh — fully automated Hysteria2 sidecar for Marzban-node.
#
# What it does automatically:
#   1. Detects node directory and data dir
#   2. Asks 2-4 questions (URL, token, domain, admin creds)
#   3. Obtains Let's Encrypt TLS cert for the node domain (via certbot)
#   4. Writes hysteria.yaml with proper TLS
#   5. Writes docker-compose.override.yml
#   6. Starts all services (docker compose up -d)
#   7. Calls the Marzban panel API to add the HYSTERIA2 host entry automatically
#      so subscriptions include the node with allowInsecure=false (or true as fallback)
#
# One-liner (fully non-interactive):
#   curl -fsSL https://raw.githubusercontent.com/MaximPyatin/Marzban-node/dev/setup-hysteria-node.sh -o /tmp/sh.sh
#   HYSTERIA2_MARZBAN_URL=https://config.the-tech.studio \
#   HYSTERIA2_HOOK_TOKEN=<token> \
#   NODE_DOMAIN=turkey.the-tech.studio \
#   PANEL_ADMIN_USER=admin \
#   PANEL_ADMIN_PASS=<password> \
#   bash /tmp/sh.sh
#
# NOTE: bash <(curl ...) does NOT work on systems where /dev/fd is restricted.
# Always download first, then run.
#
# Re-run the script on an existing node to refresh hysteria.yaml (e.g. after adding
# quic.maxIdleTimeout or resolver) and restart hysteria2.
#
# Update config only (no certbot, no panel, no questions — reads .env):
#   UPDATE_HYSTERIA_CONFIG=1 bash /tmp/sh.sh

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
if [ -z "$NODE_COMPOSE_DIR" ]; then
    for d in "${CANDIDATE_DIRS[@]}"; do
        [ -d "$d" ] && { NODE_COMPOSE_DIR="$d"; break; }
    done
fi
[ -z "$NODE_COMPOSE_DIR" ] && NODE_COMPOSE_DIR="/opt/marzban-node"

NODE_DATA_DIR="${NODE_DATA_DIR:-/var/lib/marzban-node}"
ENV_FILE="${NODE_COMPOSE_DIR}/.env"
HYSTERIA_YAML="${NODE_DATA_DIR}/hysteria.yaml"
OVERRIDE_FILE="${NODE_COMPOSE_DIR}/docker-compose.override.yml"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[hysteria-setup] $*"; }
warn() { echo "[hysteria-setup] WARN: $*"; }
err()  { echo "[hysteria-setup] ERROR: $*" >&2; exit 1; }
ok()   { echo "[hysteria-setup] ✓ $*"; }

ask() {
    # ask VAR_NAME "Prompt text" [default]
    local var="$1" prompt="$2" default="${3:-}"
    local current
    current="${!var:-}"
    [ -n "$current" ] && return   # already set via env
    current="$(env_get "$var" "$default")"
    if [ -n "$current" ]; then
        printf -v "$var" '%s' "$current"
        return
    fi
    local answer
    read -rp "  $prompt: " answer </dev/tty
    printf -v "$var" '%s' "$answer"
}

env_get() {
    local key="$1" default="${2:-}"
    if [ -f "$ENV_FILE" ]; then
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

json_value() {
    # minimal jq substitute: json_value '{"key":"val"}' key
    printf '%s' "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null || true
}

# ── banner ────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Marzban-node: Hysteria2 automated setup   ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Node dir : $NODE_COMPOSE_DIR"
echo "  Data dir : $NODE_DATA_DIR"
echo ""

# ── UPDATE_HYSTERIA_CONFIG: only refresh hysteria.yaml and restart hysteria2 ───
if [ -n "${UPDATE_HYSTERIA_CONFIG:-}" ]; then
    [ ! -f "$ENV_FILE" ] && err "No .env at ${ENV_FILE}. Run full setup first."
    HYSTERIA2_MARZBAN_URL="$(env_get HYSTERIA2_MARZBAN_URL)"
    HYSTERIA2_MARZBAN_URL="${HYSTERIA2_MARZBAN_URL%/}"
    HYSTERIA2_HOOK_TOKEN="$(env_get HYSTERIA2_HOOK_TOKEN)"
    HYSTERIA_PORT="$(env_get HYSTERIA2_PORT 2087)"
    TRAFFIC_SECRET="$(env_get HYSTERIA2_TRAFFIC_SECRET)"
    TRAFFIC_LISTEN="$(env_get HYSTERIA2_TRAFFIC_LISTEN "0.0.0.0:9999")"
    UP_MBPS="$(env_get HYSTERIA2_UP_MBPS 500)"
    DOWN_MBPS="$(env_get HYSTERIA2_DOWN_MBPS 500)"
    OBFS_PASSWORD="$(env_get HYSTERIA2_OBFS_PASSWORD)"
    CERT_FILE="${NODE_DATA_DIR}/ssl_cert.pem"
    KEY_FILE="${NODE_DATA_DIR}/ssl_key.pem"
    [ -z "$HYSTERIA2_MARZBAN_URL" ] || [ -z "$HYSTERIA2_HOOK_TOKEN" ] && err "HYSTERIA2_MARZBAN_URL and HYSTERIA2_HOOK_TOKEN must be in .env"
    log "Updating hysteria.yaml (Salamander obfs, quic maxIdleTimeout, resolver) from .env..."
    cat > "$HYSTERIA_YAML" << YAML
# Auto-generated by setup-hysteria-node.sh (UPDATE_HYSTERIA_CONFIG)

listen: ":${HYSTERIA_PORT}"

tls:
  cert: ${CERT_FILE}
  key:  ${KEY_FILE}

obfs:
  type: salamander
  salamander:
    password: ${OBFS_PASSWORD}

quic:
  maxIdleTimeout: 60s
  keepAlivePeriod: 10s

resolver:
  type: udp
  udp:
    addr: 8.8.8.8:53
    timeout: 4s

auth:
  type: http
  http:
    url: ${HYSTERIA2_MARZBAN_URL}/api/hysteria/auth?token=${HYSTERIA2_HOOK_TOKEN}
    insecure: true
    timeout: 10s

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
    log "Restarting hysteria2..."
    (cd "$NODE_COMPOSE_DIR" && docker compose restart hysteria2) || err "docker compose restart hysteria2 failed"
    ok "Config updated and hysteria2 restarted."
    exit 0
fi

# ── collect required values ───────────────────────────────────────────────────

ask HYSTERIA2_MARZBAN_URL  "Main Marzban panel URL (e.g. https://config.the-tech.studio)"
HYSTERIA2_MARZBAN_URL="${HYSTERIA2_MARZBAN_URL%/}"
[ -z "$HYSTERIA2_MARZBAN_URL" ] && err "HYSTERIA2_MARZBAN_URL is required"

ask HYSTERIA2_HOOK_TOKEN   "HYSTERIA2_HOOK_TOKEN from main Marzban .env"
[ -z "$HYSTERIA2_HOOK_TOKEN" ] && err "HYSTERIA2_HOOK_TOKEN is required"

ask NODE_DOMAIN            "This node's domain name (e.g. turkey.the-tech.studio, or press Enter to skip TLS)"
ask PANEL_ADMIN_USER       "Marzban admin username (for auto-adding host to panel, or press Enter to skip)"
if [ -n "${PANEL_ADMIN_USER:-}" ]; then
    ask PANEL_ADMIN_PASS   "Marzban admin password"
fi

HYSTERIA_PORT="${HYSTERIA2_PORT:-$(env_get HYSTERIA2_PORT 2087)}"

TRAFFIC_SECRET="$(env_get HYSTERIA2_TRAFFIC_SECRET)"
if [ -z "$TRAFFIC_SECRET" ]; then
    TRAFFIC_SECRET="$(generate_secret)"
    log "Generated HYSTERIA2_TRAFFIC_SECRET"
fi

TRAFFIC_LISTEN="$(env_get HYSTERIA2_TRAFFIC_LISTEN "0.0.0.0:9999")"
UP_MBPS="${HYSTERIA2_UP_MBPS:-$(env_get HYSTERIA2_UP_MBPS 500)}"
DOWN_MBPS="${HYSTERIA2_DOWN_MBPS:-$(env_get HYSTERIA2_DOWN_MBPS 500)}"

OBFS_PASSWORD="${HYSTERIA2_OBFS_PASSWORD:-$(env_get HYSTERIA2_OBFS_PASSWORD)}"
if [ -z "$OBFS_PASSWORD" ]; then
    OBFS_PASSWORD="$(generate_secret)"
    log "Generated HYSTERIA2_OBFS_PASSWORD (Salamander DPI obfuscation)"
fi

mkdir -p "$NODE_DATA_DIR"

# ── TLS cert ──────────────────────────────────────────────────────────────────

CERT_FILE="${NODE_DATA_DIR}/ssl_cert.pem"
KEY_FILE="${NODE_DATA_DIR}/ssl_key.pem"
USE_SELFSIGNED=true
ALLOW_INSECURE=true

if [ -n "${NODE_DOMAIN:-}" ]; then
    log "Attempting Let's Encrypt cert for ${NODE_DOMAIN}..."

    if ! command -v certbot &>/dev/null; then
        log "certbot not found — installing..."
        if command -v apt-get &>/dev/null; then
            apt-get update -qq && apt-get install -y -qq certbot
        elif command -v yum &>/dev/null; then
            yum install -y -q certbot
        else
            warn "Cannot install certbot automatically. Falling back to self-signed cert."
        fi
    fi

    if command -v certbot &>/dev/null; then
        # Stop anything on port 80 temporarily for standalone mode
        STOPPED_NGINX=false
        if systemctl is-active --quiet nginx 2>/dev/null; then
            systemctl stop nginx
            STOPPED_NGINX=true
        fi

        if certbot certonly --standalone --non-interactive --agree-tos \
            --register-unsafely-without-email \
            -d "$NODE_DOMAIN" \
            --cert-path "${NODE_DATA_DIR}/fullchain.pem" \
            --key-path  "${NODE_DATA_DIR}/privkey.pem" 2>/dev/null \
        || certbot certonly --standalone --non-interactive --agree-tos \
            --register-unsafely-without-email \
            -d "$NODE_DOMAIN" 2>/dev/null; then

            # Find where certbot stored the cert
            LE_CERT="/etc/letsencrypt/live/${NODE_DOMAIN}/fullchain.pem"
            LE_KEY="/etc/letsencrypt/live/${NODE_DOMAIN}/privkey.pem"

            if [ -f "$LE_CERT" ] && [ -f "$LE_KEY" ]; then
                CERT_FILE="$LE_CERT"
                KEY_FILE="$LE_KEY"
                USE_SELFSIGNED=false
                ALLOW_INSECURE=false
                ok "Let's Encrypt cert obtained → ${LE_CERT}"

                # Set up auto-renew hook to restart hysteriad after renewal
                HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
                mkdir -p "$HOOK_DIR"
                cat > "${HOOK_DIR}/restart-hysteria.sh" << HOOK
#!/bin/bash
cd ${NODE_COMPOSE_DIR}
docker compose restart hysteria2
HOOK
                chmod +x "${HOOK_DIR}/restart-hysteria.sh"
                ok "Auto-renewal hook installed at ${HOOK_DIR}/restart-hysteria.sh"
            fi
        else
            warn "certbot failed (port 80 blocked? DNS not set?). Falling back to self-signed cert."
        fi

        $STOPPED_NGINX && systemctl start nginx 2>/dev/null || true
    fi

    if $USE_SELFSIGNED; then
        warn "Using self-signed cert — panel host entry will be set to allowInsecure=true"
    fi
fi

# Ensure node SSL certs exist (start node once if not)
if [ ! -f "${NODE_DATA_DIR}/ssl_cert.pem" ] || [ ! -f "${NODE_DATA_DIR}/ssl_key.pem" ]; then
    warn "Node SSL certs not found. Starting marzban-node to generate them..."
    if [ -f "${NODE_COMPOSE_DIR}/docker-compose.yml" ] || [ -f "${NODE_COMPOSE_DIR}/docker-compose.yaml" ]; then
        (cd "$NODE_COMPOSE_DIR" && docker compose up -d marzban-node) || true
        log "Waiting up to 15 s for cert generation..."
        for i in $(seq 1 15); do
            sleep 1
            [ -f "${NODE_DATA_DIR}/ssl_cert.pem" ] && break
        done
    fi
    if [ ! -f "${NODE_DATA_DIR}/ssl_cert.pem" ] || [ ! -f "${NODE_DATA_DIR}/ssl_key.pem" ]; then
        err "Node SSL certs still missing after 15 s. " \
            "Start marzban-node manually, wait for it to generate certs, then re-run this script."
    fi
fi

# ── write .env ────────────────────────────────────────────────────────────────

log "Updating ${ENV_FILE}..."
env_set HYSTERIA2_ENABLED         true
env_set HYSTERIA2_PORT            "$HYSTERIA_PORT"
env_set HYSTERIA2_MARZBAN_URL     "$HYSTERIA2_MARZBAN_URL"
env_set HYSTERIA2_HOOK_TOKEN      "$HYSTERIA2_HOOK_TOKEN"
env_set HYSTERIA2_TRAFFIC_SECRET  "$TRAFFIC_SECRET"
env_set HYSTERIA2_TRAFFIC_LISTEN  "$TRAFFIC_LISTEN"
env_set HYSTERIA2_UP_MBPS         "$UP_MBPS"
env_set HYSTERIA2_DOWN_MBPS       "$DOWN_MBPS"
env_set HYSTERIA2_OBFS_PASSWORD   "$OBFS_PASSWORD"

# ── write hysteria.yaml ───────────────────────────────────────────────────────

[ -f "$HYSTERIA_YAML" ] && cp "$HYSTERIA_YAML" "${HYSTERIA_YAML}.bak"

log "Writing ${HYSTERIA_YAML}..."
cat > "$HYSTERIA_YAML" << YAML
# Auto-generated by setup-hysteria-node.sh

listen: ":${HYSTERIA_PORT}"

tls:
  cert: ${CERT_FILE}
  key:  ${KEY_FILE}

# Salamander obfuscation: disguises QUIC packets as random UDP bytes.
# DPI sees random noise instead of HTTP/3 — strongest single DPI bypass measure.
# ALL clients must configure the same obfs password in their hy2:// link.
obfs:
  type: salamander
  salamander:
    password: ${OBFS_PASSWORD}

# QUIC tuning — critical for mobile networks (CGNAT, tower switching, unstable channel)
quic:
  maxIdleTimeout: 60s
  keepAlivePeriod: 10s

# Explicit DNS so resolution does not hang on broken system resolver
resolver:
  type: udp
  udp:
    addr: 8.8.8.8:53
    timeout: 4s

auth:
  type: http
  http:
    url: ${HYSTERIA2_MARZBAN_URL}/api/hysteria/auth?token=${HYSTERIA2_HOOK_TOKEN}
    insecure: true
    timeout: 10s

bandwidth:
  up:   ${UP_MBPS} mbps
  down: ${DOWN_MBPS} mbps

trafficStats:
  listen: ${TRAFFIC_LISTEN}
  secret: ${TRAFFIC_SECRET}

# Masquerade: respond to QUIC probes like a real HTTPS/H3 website.
# TCP listeners on :80/:443 are intentionally omitted — those ports are
# typically occupied by marzban-node or nginx on the same host.
masquerade:
  type: proxy
  proxy:
    url: https://news.ycombinator.com
    rewriteHost: true
YAML
ok "hysteria.yaml written (TLS: $( $USE_SELFSIGNED && echo 'self-signed' || echo "Let's Encrypt ${NODE_DOMAIN}" ))"

# ── write docker-compose.override.yml ────────────────────────────────────────

log "Writing ${OVERRIDE_FILE}..."
LE_MOUNT=""
if ! $USE_SELFSIGNED; then
    LE_MOUNT="      - /etc/letsencrypt:/etc/letsencrypt:ro"
fi

cat > "$OVERRIDE_FILE" << COMPOSE
# Auto-generated by setup-hysteria-node.sh

services:
  hysteria2:
    image: tobyxdd/hysteria:latest
    restart: always
    network_mode: host
    volumes:
      - /var/lib/marzban-node:/var/lib/marzban-node:ro
      - /var/lib/marzban-node/hysteria.yaml:/etc/hysteria/config.yaml:ro
${LE_MOUNT}
    command: server
COMPOSE
ok "docker-compose.override.yml written."

# ── start services ────────────────────────────────────────────────────────────

log "Pulling hysteria image..."
docker pull tobyxdd/hysteria:latest -q 2>/dev/null || true

log "Starting all services..."
cd "$NODE_COMPOSE_DIR"
docker compose up -d
# Restart hysteria2 so it reloads hysteria.yaml (quic/resolver etc.)
docker compose restart hysteria2 2>/dev/null || true
ok "Services started."

# ── panel API: add HYSTERIA2 host entry ───────────────────────────────────────

add_panel_host() {
    local remark="${NODE_DOMAIN:-$(hostname)}"
    local address="${NODE_DOMAIN:-$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"
    local sni="${NODE_DOMAIN:-}"

    log "Authenticating with Marzban panel..."
    local token_resp
    token_resp=$(curl -s -k -X POST "${HYSTERIA2_MARZBAN_URL}/api/admin/token" \
        --data-urlencode "username=${PANEL_ADMIN_USER}" \
        --data-urlencode "password=${PANEL_ADMIN_PASS}" \
        --connect-timeout 10 --max-time 15 2>/dev/null || echo "")

    local access_token
    access_token=$(json_value "$token_resp" "access_token")

    if [ -z "$access_token" ]; then
        warn "Could not authenticate to panel. Check PANEL_ADMIN_USER/PANEL_ADMIN_PASS."
        warn "Add the host manually: Admin → Hosts → HYSTERIA2 → add address=${address}, port=${HYSTERIA_PORT}, allowInsecure=$ALLOW_INSECURE"
        return
    fi
    ok "Panel authentication successful."

    # Get current hosts
    local current_hosts
    current_hosts=$(curl -s -k "${HYSTERIA2_MARZBAN_URL}/api/hosts" \
        -H "Authorization: Bearer ${access_token}" \
        --connect-timeout 10 --max-time 15 2>/dev/null || echo "{}")

    # Build the new host entry for HYSTERIA2 tag (Python reads ALLOW_INSECURE from env to avoid true/True shell→Python issues)
    export ALLOW_INSECURE
    local new_host
    new_host=$(python3 - << PYEOF
import json, sys, os

current = json.loads('''${current_hosts}''')
tag = "HYSTERIA2"
hosts = current.get(tag, [])

allow_insecure = str(os.environ.get("ALLOW_INSECURE", "true")).lower() in ("1", "true", "yes")

new_entry = {
    "remark": "${remark} - HY2",
    "address": "${address}",
    "port": ${HYSTERIA_PORT},
    "sni": "${sni}",
    "host": None,
    "path": None,
    "security": "inbound_default",
    "alpn": "",
    "fingerprint": "",
    "allowinsecure": allow_insecure,
    "is_disabled": False,
    "mux_enable": False,
    "fragment_setting": None,
    "noise_setting": None,
    "random_user_agent": False,
    "use_sni_as_host": False
}

# Remove existing entry with same address to avoid duplicates
hosts = [h for h in hosts if h.get("address") != "${address}"]
hosts.append(new_entry)
current[tag] = hosts

print(json.dumps(current))
PYEOF
)

    if [ -z "$new_host" ]; then
        warn "Failed to build host JSON. Add manually in panel."
        return
    fi

    local put_resp
    put_resp=$(curl -s -k -X PUT "${HYSTERIA2_MARZBAN_URL}/api/hosts" \
        -H "Authorization: Bearer ${access_token}" \
        -H "Content-Type: application/json" \
        -d "$new_host" \
        --connect-timeout 10 --max-time 15 2>/dev/null || echo "")

    if echo "$put_resp" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'HYSTERIA2' in d else 1)" 2>/dev/null; then
        ok "Panel host entry added: HYSTERIA2 → ${address}:${HYSTERIA_PORT} (allowInsecure=${ALLOW_INSECURE})"
    else
        warn "Panel host update returned unexpected response. Check manually."
        warn "Response: $(echo "$put_resp" | head -c 200)"
    fi
}

if [ -n "${PANEL_ADMIN_USER:-}" ] && [ -n "${PANEL_ADMIN_PASS:-}" ]; then
    add_panel_host
else
    warn "PANEL_ADMIN_USER not set — skipping panel host registration."
    warn "Add manually: Admin → Hosts → HYSTERIA2 → address=${NODE_DOMAIN:-<node_ip>}, port=${HYSTERIA_PORT}, allowInsecure=${ALLOW_INSECURE}"
fi

# ── verify ────────────────────────────────────────────────────────────────────

echo ""
log "Waiting 5 s for hysteriad to initialize..."
sleep 5

log "Container status:"
(cd "$NODE_COMPOSE_DIR" && docker compose ps) || true

echo ""
log "hysteriad logs:"
(cd "$NODE_COMPOSE_DIR" && docker compose logs --tail=15 hysteria2 2>/dev/null) || true

echo ""
log "Testing auth endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${HYSTERIA2_MARZBAN_URL}/api/hysteria/auth?token=${HYSTERIA2_HOOK_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"addr":"127.0.0.1:1","auth":"probe","id":"probe"}' \
    --connect-timeout 5 --max-time 10 -k 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ]; then
    ok "Auth endpoint reachable (HTTP ${HTTP_CODE})"
else
    warn "Auth endpoint returned HTTP ${HTTP_CODE} — check HYSTERIA2_HOOK_TOKEN and panel URL"
fi

# ── done ──────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║                    Done!                    ║"
echo "╚══════════════════════════════════════════════╝"
log "  Hysteria2 port  : ${HYSTERIA_PORT}"
log "  TLS             : $( $USE_SELFSIGNED && echo 'self-signed (allowInsecure=true)' || echo "Let's Encrypt (${NODE_DOMAIN})" )"
log "  Auth URL        : ${HYSTERIA2_MARZBAN_URL}"
log "  Traffic stats   : ${TRAFFIC_LISTEN}"
log "  Salamander obfs : enabled"
log "  Obfs password   : ${OBFS_PASSWORD}"
log "  Traffic stats   : ${TRAFFIC_LISTEN}  (protected by HYSTERIA2_TRAFFIC_SECRET)"
echo "  IMPORTANT: port 9999 must be reachable from your Marzban panel IP."
echo "  Firewall example: ufw allow from <panel-ip> to any port 9999"
echo ""
echo "  ⚠  IMPORTANT — DPI obfuscation requires client-side config:"
echo "     Add these params to the hy2:// link (or your xray_config.json inbound):"
echo "       obfs=salamander"
echo "       obfs-password=${OBFS_PASSWORD}"
echo "     Without this clients will NOT connect when obfs is active."
echo ""
