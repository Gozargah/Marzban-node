#!/usr/bin/env bash
# deploy-marzban-node.sh — развёртывание / обновление Marzban-node с форка
# Поддерживает первичную установку (SSL cert, Hysteria2) и обновление.
#
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/MaximPyatin/Marzban-node/dev/deploy-marzban-node.sh \
#        -o /tmp/deploy-marzban-node.sh
#   bash /tmp/deploy-marzban-node.sh
#
# Переменные окружения:
#   NODE_COMPOSE_DIR=/Marzban-node          каталог (авто-поиск)
#   FORK_REPO=https://github.com/MaximPyatin/Marzban-node.git
#   FORK_BRANCH=dev
#   SKIP_COMPOSE=1                          только git, без docker compose
#   NO_AUTO_STASH=1                         не stash'ить docker-compose.yml
#   CLONE_IF_EMPTY=1                        клонировать, если каталог пустой
#   PANEL_CERT_URL=https://panel/ssl_cert   URL для скачивания cert панели
#   PANEL_IP=1.2.3.4                        IP панели (для firewall hint)

set -euo pipefail

FORK_REPO="${FORK_REPO:-https://github.com/MaximPyatin/Marzban-node.git}"
FORK_BRANCH="${FORK_BRANCH:-dev}"
FORK_REMOTE="${FORK_REMOTE:-fork}"

log()  { echo "[deploy-marzban-node] $*"; }
warn() { echo "[deploy-marzban-node] WARN: $*" >&2; }
err()  { echo "[deploy-marzban-node] ERROR: $*" >&2; exit 1; }
ok()   { echo "[deploy-marzban-node] ✓ $*"; }
sep()  { echo "────────────────────────────────────────────────────"; }

DATA_DIR="/var/lib/marzban-node"
DATA_ENV="${DATA_DIR}/.env"
CLIENT_CERT="${DATA_DIR}/ssl_client_cert.pem"

# ── Найти каталог с docker-compose.yml ───────────────────────────────────────

CANDIDATE_DIRS=(
    "${NODE_COMPOSE_DIR:-}"
    "/Marzban-node"
    "/opt/marzban-node"
    "/opt/Marzban-node"
    "/root/Marzban-node"
    "/root/marzban-node"
    "$(pwd)"
)

NODE_COMPOSE_DIR=""
for d in "${CANDIDATE_DIRS[@]}"; do
    [ -z "$d" ] && continue
    if [ -f "$d/docker-compose.yml" ] || [ -f "$d/docker-compose.yaml" ]; then
        NODE_COMPOSE_DIR="$d"
        break
    fi
done

if [ -z "$NODE_COMPOSE_DIR" ]; then
    err "Не найден docker-compose.yml. Установите NODE_COMPOSE_DIR=/path/to/Marzban-node или перейдите в каталог ноды."
fi

log "Каталог ноды: $NODE_COMPOSE_DIR"
cd "$NODE_COMPOSE_DIR"

# ── Git: обновление с форка ───────────────────────────────────────────────────

STASHED=0
stash_compose_if_needed() {
    [ -n "${NO_AUTO_STASH:-}" ] && return 0
    if [ -f docker-compose.yml ] && ! git diff --quiet -- docker-compose.yml 2>/dev/null; then
        log "Сохраняю локальные изменения docker-compose.yml в stash..."
        git stash push -m "deploy-marzban-node auto $(date -Iseconds 2>/dev/null || date)" -- docker-compose.yml
        STASHED=1
    fi
}

if [ ! -d .git ]; then
    if [ -n "${CLONE_IF_EMPTY:-}" ] && [ -z "$(ls -A 2>/dev/null)" ]; then
        log "Клонирование $FORK_REPO ветка $FORK_BRANCH ..."
        git clone --branch "$FORK_BRANCH" --depth 1 "$FORK_REPO" .
        ok "Клонирование завершено"
    else
        err "В $NODE_COMPOSE_DIR нет .git. Варианты:\n  1) git clone -b $FORK_BRANCH $FORK_REPO $NODE_COMPOSE_DIR\n  2) CLONE_IF_EMPTY=1 bash ... (каталог должен быть пустым)"
    fi
fi

if ! git remote get-url "$FORK_REMOTE" &>/dev/null; then
    log "Добавляю remote $FORK_REMOTE -> $FORK_REPO"
    git remote add "$FORK_REMOTE" "$FORK_REPO"
fi

log "git fetch $FORK_REMOTE $FORK_BRANCH..."
git fetch "$FORK_REMOTE" "$FORK_BRANCH"

stash_compose_if_needed

if git show-ref --verify --quiet "refs/remotes/$FORK_REMOTE/$FORK_BRANCH" 2>/dev/null; then
    log "Переключение на $FORK_BRANCH <- $FORK_REMOTE/$FORK_BRANCH ..."
    git checkout -B "$FORK_BRANCH" "$FORK_REMOTE/$FORK_BRANCH"
else
    err "Нет refs/remotes/$FORK_REMOTE/$FORK_BRANCH. Проверьте FORK_REPO и FORK_BRANCH."
fi

ok "Ветка $FORK_BRANCH, коммит $(git rev-parse --short HEAD)"

if [ -f node_metrics.py ]; then
    ok "node_metrics.py на месте"
else
    warn "node_metrics.py не найден"
fi

# ── Создать /var/lib/marzban-node/.env если нет ───────────────────────────────

if ! mkdir -p "$DATA_DIR" 2>/dev/null; then
    sudo mkdir -p "$DATA_DIR"
fi
if [ ! -f "$DATA_ENV" ]; then
    log "Создаю $DATA_ENV..."
    if ! touch "$DATA_ENV" 2>/dev/null; then
        sudo touch "$DATA_ENV"
    fi
fi

# ── Проверка SSL_CLIENT_CERT_FILE (КРИТИЧНО: без него нода не запустится) ─────

sep
if [ -f "$CLIENT_CERT" ] && [ -s "$CLIENT_CERT" ]; then
    ok "ssl_client_cert.pem найден ($(wc -l < "$CLIENT_CERT") строк)"
else
    warn "ssl_client_cert.pem отсутствует или пустой: $CLIENT_CERT"
    echo ""
    echo "  Нода НЕ запустится без сертификата панели (mTLS)."
    echo "  Это сертификат вашей Marzban ПАНЕЛИ, не ноды."
    echo ""

    # Попытка скачать cert с URL (если задан)
    if [ -n "${PANEL_CERT_URL:-}" ]; then
        log "Пробую скачать cert с $PANEL_CERT_URL ..."
        if curl -fsSL --connect-timeout 10 "$PANEL_CERT_URL" -o "$CLIENT_CERT" 2>/dev/null && [ -s "$CLIENT_CERT" ]; then
            ok "ssl_client_cert.pem скачан с $PANEL_CERT_URL"
        else
            warn "Не удалось скачать cert. Продолжаю без него."
            rm -f "$CLIENT_CERT"
        fi
    fi

    # Если cert всё ещё нет — показываем инструкцию
    if [ ! -s "$CLIENT_CERT" ]; then
        echo "  Как получить сертификат панели:"
        echo ""
        echo "  СПОСОБ 1 (если есть SSH доступ к серверу панели):"
        echo "    На сервере панели выполните:"
        echo "      cat /var/lib/marzban/ssl_cert.pem"
        echo "    Скопируйте вывод и на этом сервере выполните:"
        echo "      nano $CLIENT_CERT"
        echo "    Вставьте содержимое (должно начинаться с -----BEGIN CERTIFICATE-----)"
        echo ""
        echo "  СПОСОБ 2 (через Marzban UI):"
        echo "    Settings → Nodes → Add Node → скопируйте Certificate"
        echo "    Вставьте в $CLIENT_CERT"
        echo ""
        echo "  СПОСОБ 3 (curl, если панель доступна):"
        echo "    Узнайте IP/домен панели, затем:"
        echo "      PANEL_CERT_URL=https://<panel_ip>/api/node-cert \\"
        echo "        bash $0"
        echo ""
        echo "  После создания файла снова запустите этот скрипт."
        echo ""

        # Интерактивный ввод cert (если tty)
        if [ -t 0 ]; then
            echo -n "  Хотите вставить cert прямо сейчас? [y/N]: "
            read -r answer </dev/tty
            if [ "${answer,,}" = "y" ]; then
                echo "  Вставьте сертификат (-----BEGIN CERTIFICATE----- ... -----END CERTIFICATE-----)"
                echo "  Затем нажмите Enter на пустой строке, потом Ctrl+D:"
                CERT_CONTENT=$(cat </dev/tty)
                if echo "$CERT_CONTENT" | grep -q "BEGIN CERTIFICATE"; then
                    echo "$CERT_CONTENT" > "$CLIENT_CERT"
                    ok "ssl_client_cert.pem сохранён"
                else
                    warn "Не похоже на PEM-сертификат. Файл не создан."
                fi
            fi
        fi

        if [ ! -s "$CLIENT_CERT" ]; then
            warn "Продолжаю без ssl_client_cert.pem. Нода будет перезапускаться до его появления."
        fi
    fi
fi

# ── SKIP_COMPOSE ─────────────────────────────────────────────────────────────

if [ -n "${SKIP_COMPOSE:-}" ]; then
    log "SKIP_COMPOSE=1 — docker compose пропущен"
    [ "$STASHED" = 1 ] && warn "Был stash: git stash list && git stash pop"
    exit 0
fi

command -v docker >/dev/null || err "docker не найден в PATH"

compose_cmd="docker compose"
docker compose version &>/dev/null || compose_cmd="docker-compose"

# ── Сборка и запуск ──────────────────────────────────────────────────────────

sep
log "$compose_cmd build --pull marzban-node ..."
$compose_cmd build --pull marzban-node

log "$compose_cmd up -d marzban-node ..."
$compose_cmd up -d marzban-node

ok "marzban-node пересобран и запущен"

# ── Ждём старта ноды и проверяем ─────────────────────────────────────────────

sep
log "Ждём запуска (макс 20 сек)..."
NODE_OK=false
for i in $(seq 1 20); do
    sleep 1
    STATUS=$($compose_cmd ps --format json marzban-node 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('Status','') if isinstance(d,list) else d.get('Status',''))" 2>/dev/null || true)
    if echo "$STATUS" | grep -qi "running\|up"; then
        NODE_OK=true
        break
    fi
    # Детектируем быстрый exit (нет ssl_client_cert.pem)
    LOGS=$($compose_cmd logs --tail=5 marzban-node 2>/dev/null || true)
    if echo "$LOGS" | grep -q "certificate file.*missing\|SSL_CLIENT_CERT_FILE.*required"; then
        warn "Нода падает: отсутствует ssl_client_cert.pem!"
        warn "Добавьте cert панели в $CLIENT_CERT и перезапустите:"
        warn "  docker compose restart marzban-node"
        break
    fi
done

if $NODE_OK; then
    ok "marzban-node запущен"
else
    warn "Нода не запустилась за 20 сек. Проверьте логи:"
    warn "  cd $NODE_COMPOSE_DIR && $compose_cmd logs --tail=30 marzban-node"
fi

# ── Проверка Hysteria2 конфига в .env ─────────────────────────────────────────

sep
HY2_ENABLED=$(grep -E "^HYSTERIA2_ENABLED\s*=" "$DATA_ENV" 2>/dev/null | tail -1 | sed -E 's/.*=\s*//' | tr -d '"' | xargs 2>/dev/null || true)
HY2_SECRET=$(grep -E "^HYSTERIA2_TRAFFIC_SECRET\s*=" "$DATA_ENV" 2>/dev/null | tail -1 | sed -E 's/.*=\s*//' | tr -d '"' | xargs 2>/dev/null || true)

if [ "${HY2_ENABLED,,}" = "true" ] && [ -n "$HY2_SECRET" ]; then
    ok "Hysteria2: ENABLED=true, TRAFFIC_SECRET настроен (Smart DNS активен)"
else
    warn "Hysteria2 не настроен в $DATA_ENV."
    warn "Для Smart DNS балансировки запустите setup-hysteria-node.sh:"
    warn "  bash ${NODE_COMPOSE_DIR}/setup-hysteria-node.sh"
fi

# ── Итог ─────────────────────────────────────────────────────────────────────

sep
echo ""
echo "  Для проверки /metrics (нужны клиентский cert/key панели):"
echo "    curl -sk --cert CLIENT.pem --key CLIENT.key https://127.0.0.1:62050/metrics"
echo ""
echo "  Логи ноды:"
echo "    cd $NODE_COMPOSE_DIR && $compose_cmd logs -f marzban-node"
echo ""

[ "$STASHED" = 1 ] && warn "docker-compose.yml в stash: cd $NODE_COMPOSE_DIR && git stash pop"
