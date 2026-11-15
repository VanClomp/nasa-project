#!/usr/bin/env bash
# =============================================================================
# Deployment script for a Google Cloud server (Ubuntu 22.04 / 24.04 / Debian 12)
# Usage on the server:
#   chmod +x deploy_gcp.sh
#   ./deploy_gcp.sh
# =============================================================================
set -euo pipefail

echo "======================================================================"
echo " Planetary Analog Finder - deploying the cluster on a Google Cloud VM"
echo "======================================================================"

# 1. Install Docker and Docker Compose if the machine doesn't have them yet
if ! command -v docker >/dev/null 2>&1; then
    echo "[1/4] Installing the Docker engine and the Docker Compose plugin..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER" || true
    echo " -> Docker installed."
else
    echo "[1/4] Docker is already installed: $(docker --version)"
fi

# Check whether docker commands need sudo in this session
DOCKER_CMD="docker"
if ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

# 2. Prepare the volume folders
echo "[2/4] Preparing the ./data and ./certbot folders..."
mkdir -p ./data/earth ./data/moon ./data/mars ./certbot/www ./certbot/conf ./2-networker/conf.d

# 3. Build and start the containers
echo "[3/4] Building and starting the containers (docker compose up -d --build)..."
$DOCKER_CMD compose up -d --build

# 4. Check that it works
echo "[4/4] Waiting for the services to start and testing the healthcheck..."
for i in {1..15}; do
    if curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ""
echo "Container status:"
$DOCKER_CMD compose ps

echo ""
echo "Response of /api/v1/health:"
curl -s http://127.0.0.1/api/v1/health || true
echo ""

PUBLIC_IP=$(curl -s --max-time 3 https://ifconfig.me || hostname -I | awk '{print $1}')
echo "======================================================================"
echo " DONE! The app is running at:"
echo "   -> http://${PUBLIC_IP}/"
echo "   -> http://${PUBLIC_IP}/explorer.php"
echo "   -> http://${PUBLIC_IP}/api/v1/health"
echo ""
echo " Once you point a domain's A record at ${PUBLIC_IP}, run:"
echo "   ./enable_https.sh yourdomain.com you@example.com"
echo "======================================================================"
