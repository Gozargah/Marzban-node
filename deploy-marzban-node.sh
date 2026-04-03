#!/usr/bin/env bash
# deploy-marzban-node.sh — быстрое развёртывание / обновление Marzban-node с ветки форка
# (GET /metrics, node_metrics.py для Smart DNS на панели).
#
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/MaximPyatin/Marzban-node/dev/deploy-marzban-node.sh -o /tmp/deploy-marzban-node.sh
#   bash /tmp/deploy-marzban-node.sh
#
# Переменные окружения:
#   NODE_COMPOSE_DIR=/Marzban-node          каталог (по умолчанию — авто-поиск)
#   FORK_REPO=https://github.com/MaximPyatin/Marzban-node.git
#   FORK_BRANCH=dev
#   FORK_REMOTE=fork
#   SKIP_COMPOSE=1                          только git, без docker compose
#   NO_AUTO_STASH=1                         не stash'ить docker-compose.yml при изменениях
#   CLONE_IF_EMPTY=1                        если каталог пустой — git clone (создайте каталог заранее)

set -euo pipefail

FORK_REPO="${FORK_REPO:-https://github.com/MaximPyatin/Marzban-node.git}"
FORK_BRANCH="${FORK_BRANCH:-dev}"
FORK_REMOTE="${FORK_REMOTE:-fork}"

log()  { echo "[deploy-marzban-node] $*"; }
warn() { echo "[deploy-marzban-node] WARN: $*" >&2; }
err()  { echo "[deploy-marzban-node] ERROR: $*" >&2; exit 1; }
ok()   { echo "[deploy-marzban-node] ✓ $*"; }

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

STASHED=0
stash_compose_if_needed() {
    if [ -n "${NO_AUTO_STASH:-}" ]; then
        return 0
    fi
    if [ -f docker-compose.yml ] && ! git diff --quiet -- docker-compose.yml 2>/dev/null; then
        log "Сохраняю локальные изменения docker-compose.yml в stash..."
        git stash push -m "deploy-marzban-node auto $(date -Iseconds 2>/dev/null || date)" -- docker-compose.yml
        STASHED=1
    fi
}

if [ ! -d .git ]; then
    if [ -n "${CLONE_IF_EMPTY:-}" ] && [ -z "$(ls -A 2>/dev/null)" ]; then
        log "Клонирование $FORK_REPO ветка $FORK_BRANCH в $NODE_COMPOSE_DIR ..."
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

if [ -n "${SKIP_COMPOSE:-}" ]; then
    log "SKIP_COMPOSE=1 — docker compose пропущен"
    [ "$STASHED" = 1 ] && warn "Был stash: git stash list && git stash pop"
    exit 0
fi

command -v docker >/dev/null || err "docker не найден в PATH"

DATA_ENV="/var/lib/marzban-node/.env"
if [ ! -f "$DATA_ENV" ]; then
    log "Создаю $DATA_ENV — задайте HYSTERIA2_TRAFFIC_SECRET= (как trafficStats.secret в hysteria.yaml), см. .env.example"
    if ! mkdir -p /var/lib/marzban-node 2>/dev/null || ! touch "$DATA_ENV" 2>/dev/null; then
        sudo mkdir -p /var/lib/marzban-node
        sudo touch "$DATA_ENV"
    fi
fi

compose_cmd="docker compose"
docker compose version &>/dev/null || compose_cmd="docker-compose"

log "$compose_cmd build --pull marzban-node ..."
$compose_cmd build --pull marzban-node

log "$compose_cmd up -d marzban-node ..."
$compose_cmd up -d marzban-node

ok "marzban-node пересобран и запущен"

[ "$STASHED" = 1 ] && warn "docker-compose.yml в stash: cd $NODE_COMPOSE_DIR && git stash pop"

log "Проверка /metrics: curl -sk --cert CLIENT.pem --key CLIENT.key https://127.0.0.1:62050/metrics"
