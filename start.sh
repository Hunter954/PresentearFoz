#!/bin/sh
set -eu

PORT="${PORT:-8080}"
export PORT

mkdir -p "${UPLOAD_FOLDER:-/data/uploads}"

echo "[startup] Iniciando preparação do banco..."
python startup.py

echo "[startup] Iniciando Gunicorn na porta ${PORT}..."
exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
