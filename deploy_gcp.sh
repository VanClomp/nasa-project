#!/usr/bin/env bash
# =============================================================================
# Skrypt wdrożeniowy na serwer Google Cloud (Ubuntu 22.04 / 24.04 / Debian 12)
# Użycie na serwerze:
#   chmod +x deploy_gcp.sh
#   ./deploy_gcp.sh
# =============================================================================
set -euo pipefail

echo "======================================================================"
echo " Planetary Analog Finder - Wdrożenie klastra na Google Cloud VM"
echo "======================================================================"

# 1. Instalacja Dockera i Docker Compose, jeśli jeszcze ich nie ma na maszynie
if ! command -v docker >/dev/null 2>&1; then
    echo "[1/4] Instalacja silnika Docker oraz wtyczki Docker Compose..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER" || true
    echo " -> Docker został zainstalowany."
else
    echo "[1/4] Docker jest już zainstalowany: $(docker --version)"
fi

# Sprawdzenie czy potrzebujemy sudo do poleceń dockera w bieżącej sesji
DOCKER_CMD="docker"
if ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

# 2. Przygotowanie katalogów wolumenów
echo "[2/4] Przygotowanie struktury katalogów ./data oraz ./certbot..."
mkdir -p ./data/earth ./data/moon ./data/mars ./certbot/www ./certbot/conf ./2-networker/conf.d

# 3. Budowanie i uruchomienie kontenerów
echo "[3/4] Budowanie i uruchamianie kontenerów (docker compose up -d --build)..."
$DOCKER_CMD compose up -d --build

# 4. Weryfikacja działania
echo "[4/4] Oczekiwanie na uruchomienie serwisów i test healthcheck..."
for i in {1..15}; do
    if curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ""
echo "Status kontenerów:"
$DOCKER_CMD compose ps

echo ""
echo "Odpowiedź /api/v1/health:"
curl -s http://127.0.0.1/api/v1/health || true
echo ""

PUBLIC_IP=$(curl -s --max-time 3 https://ifconfig.me || hostname -I | awk '{print $1}')
echo "======================================================================"
echo " GOTOWE! Aplikacja działa pod adresem:"
echo "   -> http://${PUBLIC_IP}/"
echo "   -> http://${PUBLIC_IP}/explorer.php"
echo "   -> http://${PUBLIC_IP}/api/v1/health"
echo ""
echo " Gdy kupisz domenę i przekierujesz rekord A na ${PUBLIC_IP}, uruchom:"
echo "   ./enable_https.sh twojadomena.pl twoj@email.com"
echo "======================================================================"
