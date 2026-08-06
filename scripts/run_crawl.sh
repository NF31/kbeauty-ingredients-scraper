#!/usr/bin/env bash
# Lance le spider uniikon_gammes de facon non-interactive (cron).
#
# S'assure d'abord que Cassandra tourne : un `docker compose up -d` a
# ete lance a la main jusqu'ici, mais cron peut se declencher apres un
# redemarrage WSL sans qu'on ait repense a relancer le container.
set -euo pipefail

PROJECT_DIR="/home/nf21/projects/kbeauty-ingredients-scraper"
ECOSYSTEM_DIR="/home/nf21/projects/kbeauty-ecosystem"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

if ! /usr/bin/docker ps --filter "name=kbeauty_cassandra" --filter "status=running" --format '{{.Names}}' | grep -q kbeauty_cassandra; then
    /usr/bin/docker compose -f "$ECOSYSTEM_DIR/docker-compose.yml" up -d cassandra
    sleep 15
fi

cd "$PROJECT_DIR"
source .venv/bin/activate

scrapy crawl uniikon_gammes \
    -L INFO \
    --logfile "$LOG_DIR/uniikon_gammes_$(date +%Y%m%d_%H%M%S).log"
