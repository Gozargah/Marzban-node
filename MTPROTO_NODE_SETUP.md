# MTProto Node Setup

## 1. На узле

```bash
cd /opt/marzban-node
bash ./setup-mtproto-node.sh
```

Ответь на вопросы:
- `MTPROTO_DOMAIN` = домен узла, например `tg.the-tech.studio`
- `MTPROTO_PORT` = порт, например `1443`
- `MTPROTO_MODE` = `dd`

Проверка:

```bash
cd /opt/marzban-node
docker compose ps mtproto
docker compose logs --tail=50 mtproto
```

## 2. На основном хосте Marzban

В `.env`:

```env
MTPROTO_NODE_NAME=<имя этого узла в панели Marzban>
MTPROTO_PUBLIC_HOST=tg.the-tech.studio
MTPROTO_PUBLIC_PORT=1443
MTPROTO_SECRET_MODE=dd
```

Перезапуск:

```bash
cd /opt/marzban
docker compose up -d
```

## 3. Проверка синхронизации

После перезапуска основного хоста:

```bash
cd /opt/marzban-node
docker compose logs --tail=100 mtproto
```

Должно появиться:
- лог про `MTProto config synced`
- ссылки `telemt::links` с `server=tg.the-tech.studio`

## 4. Проверка API на хосте

У пользователя должен возвращаться домен узла:

```text
tg://proxy?server=tg.the-tech.studio&port=1443&secret=dd...
```
