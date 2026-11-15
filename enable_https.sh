#!/usr/bin/env bash
# =============================================================================
# Automatic setup of a free SSL certificate (Let's Encrypt) for a domain
# Usage (after pointing the domain's DNS A record at the GCP server's IP):
#   chmod +x enable_https.sh
#   ./enable_https.sh yourdomain.com you@example.com
# =============================================================================
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 analogfinder.com contact@analogfinder.com"
    exit 1
fi

DOMAIN="$1"
EMAIL="$2"

DOCKER_CMD="docker"
if ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

mkdir -p ./certbot/www ./certbot/conf ./2-networker/conf.d

echo "[1/3] Requesting a Let's Encrypt certificate for ${DOMAIN}..."
$DOCKER_CMD run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly --webroot \
    -w /var/www/certbot \
    -d "${DOMAIN}" \
    --email "${EMAIL}" \
    --agree-tos \
    --no-eff-email \
    --non-interactive

echo "[2/3] Generating the Nginx HTTPS config (2-networker/conf.d/ssl.conf)..."
cat > ./2-networker/conf.d/ssl.conf <<EOF
server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 30s;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host \$host;
    }

    location / {
        rewrite ^/(moon_photo|mars_photo|earth_photo|sky_photo)\.jpg$ /images/$1.jpg break;
        proxy_pass http://frontend:80;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF

echo "[3/3] Reloading Nginx in the networker container..."
$DOCKER_CMD compose exec networker nginx -s reload

echo "======================================================================"
echo " SUKCES! Certyfikat SSL aktywny: https://${DOMAIN}/"
echo "======================================================================"
