#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/dot_ch_radio_docker}"
mkdir -p "$DOCKER_CONFIG"

docker compose up -d --build dot_ch_radio
docker compose ps dot_ch_radio
