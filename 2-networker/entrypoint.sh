#!/bin/sh
set -e

mkdir -p /var/www/certbot /etc/nginx/conf.d

echo "[2-networker] Uruchamianie serwisu FastAPI na 127.0.0.1:8000..."
uvicorn networker.api:app --host 127.0.0.1 --port 8000 --workers "${NETWORKER_WORKERS:-2}" &
UVICORN_PID=$!

echo "[2-networker] Uruchamianie Nginx Reverse Proxy na porcie 80/443..."
nginx -g "daemon off;" &
NGINX_PID=$!

trap 'kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true' INT TERM

# Czekaj na zakończenie któregokolwiek procesu
while kill -0 "$UVICORN_PID" 2>/dev/null && kill -0 "$NGINX_PID" 2>/dev/null; do
    sleep 2
done

echo "[2-networker] Jeden z procesów zakończył działanie. Zatrzymywanie kontenera..."
kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
exit 1
