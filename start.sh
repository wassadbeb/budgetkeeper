#!/usr/bin/env bash
# Запуск BudgetKeeper: PostgreSQL (TCP 127.0.0.1:5432) + миграции + сервер Django.
set -e
cd "$(dirname "$0")"

source .venv/bin/activate

PG_BIN=".venv/lib/python3.12/site-packages/pgserver/pginstall/bin"
PGDATA="/private/var/folders/wq/8wwvc9nj0cg0r9x_2knv9jlc0000gn/T/opencode/pgdata"

# 1. PostgreSQL: инициализация (если нужно) и запуск по TCP.
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  echo "==> Инициализация PostgreSQL ..."
  "$PG_BIN/initdb" --auth=trust --auth-local=trust --encoding=utf8 -U postgres -D "$PGDATA" >/dev/null
fi
if ! "$PG_BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
  echo "==> Запуск PostgreSQL (127.0.0.1:5432) ..."
  "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/log" -o "-h 127.0.0.1 -p 5432 -k $PGDATA" -w start >/dev/null
fi

# 2. Миграции и демо-данные (идемпотентно).
echo "==> Применение миграций ..."
python manage.py migrate

echo "==> Демо-данные (пропускается, если уже есть) ..."
python manage.py seed_demo || true

# 3. Сервер разработки.
echo "==> Запуск Django: http://127.0.0.1:8000/"
echo "    Демо: demo@budgetkeeper.ru / Demo12345!"
echo "    Админ: admin@budgetkeeper.ru / Admin12345!"
echo "    БД (pgAdmin): 127.0.0.1:5432, база budgetkeeper, пользователь postgres"
echo "    Остановить: Ctrl+C"
exec python manage.py runserver 127.0.0.1:8000
