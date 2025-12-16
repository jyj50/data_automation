#!/bin/sh
set -euo pipefail

: "${PORT:=8000}"
: "${MEDIA_ROOT:=/app/media}"

mkdir -p "${MEDIA_ROOT}"

if [ -n "${SQLITE_PATH:-}" ]; then
    mkdir -p "$(dirname "${SQLITE_PATH}")"
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
