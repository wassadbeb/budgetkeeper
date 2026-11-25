#!/usr/bin/env bash
# Запуск BudgetKeeper: PostgreSQL (pgserver) + миграции + сервер Django.
# Работает на машине, где уже создано окружение .venv (Python 3.12 + pgserver).
set -e
cd "$(dirname "$0")"

source .venv/bin/activate

# 1. PostgreSQL. Путь к данным берём из .env (переменная DB_HOST).
#    Если DB_HOST — это путь к каталогу (начинается с "/"), запускаем
#    встроенный PostgreSQL через pgserver; иначе предполагаем обычный сервер.
PGDATA=$(grep -E '^DB_HOST=' .env | cut -d= -f2-)
if [[ "$PGDATA" == /* ]]; then
  echo "==> Запуск PostgreSQL (pgdata: $PGDATA) ..."
  PGDATA="$PGDATA" python - <<'PY'
import os
from pathlib import Path
from pgserver import PostgresServer

s = PostgresServer(Path(os.environ["PGDATA"]), cleanup_mode=None)
s.ensure_pgdata_inited()
s.ensure_postgres_running()
print("PostgreSQL готов:", s.get_uri())
PY
else
  echo "==> Используется внешний PostgreSQL ($PGDATA) — убедитесь, что он запущен."
fi

# 2. Миграции и демо-данные (идемпотентно)
echo "==> Применение миграций ..."
python manage.py migrate

echo "==> Демо-данные (пропускается, если уже есть) ..."
python manage.py seed_demo || true

# 3. Сервер разработки
echo "==> Запуск Django: http://127.0.0.1:8000/"
echo "    Демо: demo@budgetkeeper.ru / Demo12345!"
echo "    Админ: admin@budgetkeeper.ru / Admin12345!"
echo "    Остановить: Ctrl+C"
exec python manage.py runserver 127.0.0.1:8000
