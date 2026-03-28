# MTProto On Marzban-node

## Что это делает

Эта реализация переносит MTProto data-plane на один выбранный `Marzban-node`.

Итоговая схема такая:

- основной хост `Marzban` не поднимает локальный `mtproto` контейнер
- основной хост остается control-plane:
  - проверяет, доступен ли MTProto пользователю
  - генерирует `password` и `secret`
  - отдает `tg://proxy?...` через API
  - синхронизирует active/on_hold пользователей на один выбранный узел
- выбранный `Marzban-node` поднимает:
  - основной контейнер `marzban-node`
  - sidecar `mtproto` с `telemt`
- `telemt` обслуживает реальные MTProto подключения клиентов

## Как это работает

### На основном хосте `Marzban`

Хост:

- хранит `MTPROTO_NODE_NAME`
- хранит `MTPROTO_PUBLIC_HOST`
- хранит `MTPROTO_PUBLIC_PORT`
- генерирует per-user raw secret
- при старте и изменении пользователей отправляет список MTProto-пользователей на выбранный узел

Если на хосте нет этих переменных, MTProto считается выключенным.

### На узле `Marzban-node`

Узел:

- принимает запрос `/mtproto/apply` от основного хоста
- по списку пользователей формирует `/var/lib/marzban-node/mtproto/telemt.toml`
- sidecar `mtproto` ждет этот файл
- как только файл появляется, `telemt` стартует и начинает слушать MTProto порт

Это важно:

- если `telemt.toml` нет, контейнер `mtproto` может быть `Up`, но MTProto реально не работает
- если основной `marzban-node` не видит `MTPROTO_ENABLED=true`, он будет отвечать `404` на `/mtproto/apply`

## Пути

В этой инструкции используются реальные пути из твоего кейса:

- основной хост: `/opt/marzban`
- узел: `~/Marzban-node`
- node data dir: `/var/lib/marzban-node`
- MTProto config на узле: `/var/lib/marzban-node/mtproto/telemt.toml`

## Требования

Перед началом должно быть:

1. На основном хосте уже обновлен `Marzban` с поддержкой node-side MTProto sync.
2. На узле уже существует рабочий `Marzban-node`.
3. Узел подключен в панели и имеет точное имя, например `tg`.
4. Домен узла уже смотрит на IP этого узла.
5. Порт MTProto открыт на узле, например `1443/tcp`.

## Рекомендуемый режим

Для твоего случая использовать:

```env
MTPROTO_SECRET_MODE=dd
MTPROTO_USE_MIDDLE_PROXY=false
MTPROTO_LISTEN_ADDR_IPV4=0.0.0.0
MTPROTO_IPV6_ENABLED=false
MTPROTO_NETWORK_PREFER=4
MTPROTO_SHOW_LINKS=false
MTPROTO_LOG_LEVEL=normal
MTPROTO_RUST_LOG=info,telemt::links=warn
MTPROTO_RELOAD_INTERVAL=5
MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15
MTPROTO_TG_CONNECT_TIMEOUT=10
MTPROTO_CLIENT_KEEPALIVE_TIMEOUT=60
MTPROTO_CLIENT_ACK_TIMEOUT=300
```

Не использовать `ee`, если нет отдельного корректного TLS-сценария под этот режим.

Это дает production-safe runtime для `telemt`:

- IPv4-only без неявных fallback
- явный bind на `0.0.0.0`
- явные таймауты для handshake и соединения с Telegram
- configurable `middle proxy`, а не hardcoded поведение
- `tg://` links не печатаются в production logs по умолчанию

## Что именно нужно развернуть

Нужно развернуть две части.

### Часть 1. Основной хост

На хосте должны быть заданы:

```env
MTPROTO_NODE_NAME=tg
MTPROTO_PUBLIC_HOST=tg.the-tech.studio
MTPROTO_PUBLIC_PORT=1443
MTPROTO_SECRET_MODE=dd
```

Где:

- `MTPROTO_NODE_NAME` — точное имя узла из панели
- `MTPROTO_PUBLIC_HOST` — домен узла, по которому клиент будет подключаться
- `MTPROTO_PUBLIC_PORT` — порт MTProto на узле
- `MTPROTO_SECRET_MODE` — `dd`

На хосте локальный `mtproto` контейнер не нужен.

### Часть 2. Узел

На узле:

- основной контейнер `marzban-node` должен быть собран из ветки `mtproto`
- sidecar `mtproto` должен быть поднят через `docker-compose.override.yml`
- основной контейнер `marzban-node` должен получать `.env` через `env_file: .env`
- `telemt.toml` должен рендериться уже не как bare minimum, а с `[network]`, `[server]`, `[timeouts]`

Это критично. Если `env_file: .env` не подключен к сервису `marzban-node`, тогда:

- в контейнере нет `MTPROTO_ENABLED=true`
- `/mtproto/apply` отвечает `404`
- `telemt.toml` не создается
- MTProto не стартует

## Развертывание на узле

### 1. Перейти в каталог узла

```bash
cd ~/Marzban-node
```

### 2. Переключиться на ветку `mtproto`

Если ветка еще не переключена:

```bash
git fetch https://github.com/MaximPyatin/Marzban-node.git mtproto
git checkout -B mtproto FETCH_HEAD
```

### 3. Запустить setup script

```bash
bash ./setup-mtproto-node.sh
```

Скрипт:

- создает/обновляет `.env`
- выставляет `MTPROTO_ENABLED=true`
- пишет runtime defaults для `telemt`
- пишет `docker-compose.override.yml`
- собирает и запускает sidecar `mtproto`

### 4. Ответы для `dd`

На вопросы отвечать так:

```text
MTPROTO_DOMAIN=tg.the-tech.studio
MTPROTO_PORT=1443
MTPROTO_MODE=dd
```

После скрипта в `.env` также должны быть:

```env
MTPROTO_USE_MIDDLE_PROXY=false
MTPROTO_LISTEN_ADDR_IPV4=0.0.0.0
MTPROTO_IPV6_ENABLED=false
MTPROTO_NETWORK_PREFER=4
MTPROTO_SHOW_LINKS=false
MTPROTO_LOG_LEVEL=normal
MTPROTO_RUST_LOG=info,telemt::links=warn
MTPROTO_RELOAD_INTERVAL=5
MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15
MTPROTO_TG_CONNECT_TIMEOUT=10
MTPROTO_CLIENT_KEEPALIVE_TIMEOUT=60
MTPROTO_CLIENT_ACK_TIMEOUT=300
```

### 5. Убедиться, что основной `marzban-node` тоже читает `.env`

Открой:

```bash
nano ~/Marzban-node/docker-compose.yml
```

У сервиса `marzban-node` должно быть:

```yaml
services:
  marzban-node:
    build: .
    restart: always
    env_file: .env
    network_mode: host
```

Если строки `env_file: .env` нет, добавь ее.

### 6. Пересобрать основной контейнер узла

```bash
cd ~/Marzban-node
docker compose down
docker compose up -d --build marzban-node mtproto
```

## Развертывание на основном хосте

### 1. Перейти в каталог

```bash
cd /opt/marzban
```

### 2. Убедиться, что `.env` уже содержит

```env
MTPROTO_NODE_NAME=tg
MTPROTO_PUBLIC_HOST=tg.the-tech.studio
MTPROTO_PUBLIC_PORT=1443
MTPROTO_SECRET_MODE=dd
```

Важно:

- `MTPROTO_NODE_NAME` должен совпадать с именем node в панели символ в символ
- не пиши комментарий в той же строке, например так делать нельзя:

```env
MTPROTO_NODE_NAME=tg # comment
```

Нужно только так:

```env
MTPROTO_NODE_NAME=tg
```

### 3. Перезапустить основной хост

Если образ уже обновлен:

```bash
marzban restart
```

Если нужно сначала подтянуть свежий образ:

```bash
cd /opt/marzban
docker compose pull marzban
docker compose up -d marzban
```

## Полный порядок запуска

Если делать с нуля, последовательность такая:

1. На узле обновить код и переключить `Marzban-node` на ветку `mtproto`.
2. На узле запустить `setup-mtproto-node.sh`.
3. На узле убедиться, что `docker-compose.yml` содержит `env_file: .env` у `marzban-node`.
4. На узле выполнить:

```bash
cd ~/Marzban-node
docker compose down
docker compose up -d --build marzban-node mtproto
```

5. На хосте проверить `.env`.
6. На хосте выполнить:

```bash
marzban restart
```

7. На узле проверить появление `telemt.toml`.

## Как проверить, что все реально заработало

### Проверка 1. Основной `marzban-node` видит MTProto env

На узле:

```bash
cd ~/Marzban-node
docker compose exec marzban-node env | grep MTPROTO
```

Должно быть что-то вроде:

```text
MTPROTO_ENABLED=true
MTPROTO_DOMAIN=tg.the-tech.studio
MTPROTO_PORT=1443
MTPROTO_MODE=dd
MTPROTO_USE_MIDDLE_PROXY=false
MTPROTO_LISTEN_ADDR_IPV4=0.0.0.0
MTPROTO_IPV6_ENABLED=false
MTPROTO_NETWORK_PREFER=4
MTPROTO_SHOW_LINKS=false
MTPROTO_LOG_LEVEL=normal
MTPROTO_RUST_LOG=info,telemt::links=warn
MTPROTO_RELOAD_INTERVAL=5
MTPROTO_CLIENT_HANDSHAKE_TIMEOUT=15
MTPROTO_TG_CONNECT_TIMEOUT=10
MTPROTO_CLIENT_KEEPALIVE_TIMEOUT=60
MTPROTO_CLIENT_ACK_TIMEOUT=300
MTPROTO_CONFIG_PATH=/var/lib/marzban-node/mtproto/telemt.toml
```

Если вывода нет, основной контейнер узла не читает `.env`.

### Проверка 2. На узле появился конфиг

```bash
ls -la /var/lib/marzban-node/mtproto
sed -n '1,120p' /var/lib/marzban-node/mtproto/telemt.toml
```

Если `telemt.toml` отсутствует, значит хост не смог выполнить sync.

Внутри `telemt.toml` теперь должны быть секции:

- `[general]`
- `[general.links]`
- `[network]`
- `[server]`
- `[timeouts]`
- `[access.users]`

И для твоего кейса там ожидаемо увидеть:

```toml
[network]
ipv4 = true
ipv6 = false
prefer = 4

[general.links]
show = []
public_host = "tg.example.com"
public_port = 1443

[server]
port = 1443
listen_addr_ipv4 = "0.0.0.0"

[timeouts]
client_handshake = 15
tg_connect = 10
client_keepalive = 60
client_ack = 300
```

### Проверка 3. Логи основного узла

```bash
cd ~/Marzban-node
docker compose logs --tail=200 marzban-node
```

Если хост пытается отправлять конфиг, ты увидишь:

```text
POST /mtproto/apply
```

Также узел теперь умеет отдавать effective runtime:

```bash
cd ~/Marzban-node
curl -sk https://127.0.0.1:62050/mtproto/status \
  -H 'Content-Type: application/json' \
  --data '{"session_id":"<active-session-id>"}'
```

В ответе должны быть не только `enabled/configured_users`, но и:

- `mode`
- `domain`
- `port`
- `show_links`
- `log_level`
- `rust_log`
- `use_middle_proxy`
- `listen_addr_ipv4`
- `ipv6_enabled`
- `network_prefer`
- `reload_interval`
- `client_handshake_timeout`
- `tg_connect_timeout`
- `client_keepalive_timeout`
- `client_ack_timeout`

### Проверка 4. Логи sidecar `mtproto`

```bash
cd ~/Marzban-node
docker compose logs --tail=200 mtproto
```

После успешного sync там должны появиться уже не пустые логи, а запуск `telemt`.

### Проверка 5. Порт слушается

```bash
ss -ltnp | grep 1443
```

Если `telemt` стартовал, порт начнет слушаться.

### Проверка 6. API на хосте отдает домен узла

На рабочем месте или на хосте запрос к API должен вернуть:

```text
tg://proxy?server=tg.the-tech.studio&port=1443&secret=dd...
```

## Что означает каждая типовая ошибка

### Ошибка: `MTProto proxy is not configured`

Это ошибка на основном хосте.

Значит на хосте не выполнено хотя бы одно из условий:

- не задан `MTPROTO_NODE_NAME`
- не задан `MTPROTO_PUBLIC_HOST`
- не задан `MTPROTO_PUBLIC_PORT`

### Ошибка: `Failed to sync MTProto config to node "tg": Not Found`

Это значит:

- хост дошел до узла
- но у `marzban-node` на узле еще не было route `/mtproto/apply`

Обычно это означает, что основной контейнер `marzban-node` еще работает на старом коде.

### Ошибка: `Failed to sync MTProto config to node "tg": MTProto is disabled on this node`

Это значит:

- route `/mtproto/apply` уже есть
- но в основном контейнере `marzban-node` нет `MTPROTO_ENABLED=true`

Обычно это означает, что `marzban-node` не читает `.env`, то есть в `docker-compose.yml` отсутствует:

```yaml
env_file: .env
```

### Ошибка: `Skipping MTProto sync: runtime mismatch on node`

Это новый защитный сценарий.

Значит host и node расходятся хотя бы по одному из полей:

- `MTPROTO_SECRET_MODE` на хосте не совпадает с `MTPROTO_MODE` на узле
- `MTPROTO_PUBLIC_HOST` на хосте не совпадает с `MTPROTO_DOMAIN` на узле
- `MTPROTO_PUBLIC_PORT` на хосте не совпадает с `MTPROTO_PORT` на узле

Пока это не выровнено, host больше не пушит MTProto users вслепую.

### Контейнер `mtproto` в статусе `Up`, но логов нет

Это значит:

- sidecar жив
- но `telemt.toml` еще не создан
- `telemt` внутри еще не стартовал

Это нормальное поведение до первого успешного sync с хоста.

### `telemt.toml` нет и `ss -ltnp | grep 1443` ничего не показывает

Это значит:

- sync от хоста еще не прошел
- реального MTProto listener еще нет

### В логах есть `telemt::links` с полными `tg://proxy?...secret=...`

Это плохой признак для production.

Значит отключены безопасные logging defaults, и secrets утекают в container logs.

Проверь, что на узле выставлено:

```env
MTPROTO_SHOW_LINKS=false
MTPROTO_RUST_LOG=info,telemt::links=warn
```

### Build `telemt` идет очень долго

Первый build может идти долго, потому что:

- `telemt` собирается из Rust исходников
- на слабом VPS это нормально
- это не ошибка, если build в итоге заканчивается успешно

## Быстрая диагностика

Если что-то не работает, выполняй в таком порядке.

### На хосте

```bash
cd /opt/marzban
docker logs --tail=200 marzban-marzban-1 | grep -i mtproto
```

### На узле

```bash
cd ~/Marzban-node
docker compose exec marzban-node env | grep MTPROTO
docker compose logs --tail=200 marzban-node
ls -la /var/lib/marzban-node/mtproto
sed -n '1,120p' /var/lib/marzban-node/mtproto/telemt.toml
docker compose logs --tail=200 mtproto
ss -ltnp | grep 1443
```

## Как читать telemt логи

- `telemt::links` или startup-список пользователей:
  это не признак ошибки маршрутизации. Это только факт, что sidecar загрузил конфиг. В production эти логи лучше держать выключенными.
- `config reload`, `users removed`, `users added`:
  sync с хоста работает, hot reload работает.
- `telemt::proxy::relay: Activity timeout ... idle_secs=1800`:
  это значит, что реальные сессии доходят до relay-стадии. То есть проблема не в broken secret generation.
- `Host is unreachable (os error 113)` сериями:
  это уже symptom исходящего пути `tg-node -> Telegram`.
- `Operation timed out (os error 110)` сериями:
  это тоже symptom исходящего пути `tg-node -> Telegram`, а не сбой sync.
- `Telegram handshake timeout`:
  клиент дошел до sidecar, но sidecar не смог нормально завершить upstream Telegram stage в отведенный таймаут.
- `early eof` единично:
  обычно клиент/сканер/оборванная попытка, а не массовая причина деградации.

## Минимальный рабочий чеклист

Перед тем как тестировать `tg://proxy?...`, должно быть выполнено все ниже:

- основной хост знает `MTPROTO_NODE_NAME`
- основной хост знает `MTPROTO_PUBLIC_HOST`
- основной хост знает `MTPROTO_PUBLIC_PORT`
- node в панели называется ровно так же, как в `MTPROTO_NODE_NAME`
- основной `marzban-node` на узле запущен из новой ветки
- основной `marzban-node` читает `.env`
- `/var/lib/marzban-node/mtproto/telemt.toml` существует
- `docker compose logs mtproto` уже не пустой
- `ss -ltnp | grep 1443` показывает listener

Пока хотя бы один из этих пунктов не выполнен, клиентский `tg://proxy?...` может не подключаться.

## Самая короткая рабочая последовательность

### На узле

```bash
cd ~/Marzban-node
git fetch https://github.com/MaximPyatin/Marzban-node.git mtproto
git checkout -B mtproto FETCH_HEAD
bash ./setup-mtproto-node.sh
```

Потом убедиться, что в `docker-compose.yml` есть:

```yaml
env_file: .env
```

Потом:

```bash
cd ~/Marzban-node
docker compose down
docker compose up -d --build marzban-node mtproto
```

### На хосте

```bash
marzban restart
```

### Снова на узле

```bash
cd ~/Marzban-node
ls -la /var/lib/marzban-node/mtproto
sed -n '1,120p' /var/lib/marzban-node/mtproto/telemt.toml
docker compose logs --tail=100 mtproto
ss -ltnp | grep 1443
```

## Ожидаемый результат

Когда все работает, будет так:

1. На хосте API отдает:

```text
tg://proxy?server=tg.the-tech.studio&port=1443&secret=dd...
```

2. На узле существует файл:

```text
/var/lib/marzban-node/mtproto/telemt.toml
```

3. На узле `mtproto` контейнер пишет рабочие логи `telemt`.

4. На узле порт `1443` слушается.

5. Клиент Telegram подключается по домену узла.
