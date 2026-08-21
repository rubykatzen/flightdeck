#!/bin/bash
set -e

ensure_network() {
  local network="$1"

  if ! docker network inspect "$network" >/dev/null 2>&1; then
    docker network create "$network" >/dev/null
    echo "Created Docker network: $network"
  fi
}

source "$(dirname "$0")/lib.sh"

mkdir -p apps-data/traefik
touch apps-data/traefik/acme.json
chmod 600 apps-data/traefik/acme.json
ensure_network traefik
ensure_network databases
ensure_network mcp

set -a
source .env
set +a

if [ $# -gt 0 ]; then
  apps=("$@")
else
  parse_apps "$APPS"
fi

for app in "${apps[@]}"
do
  (
    echo "Starting: ${app}"

    require_app_compose "${app}"
    if [ -z "${FLIGHTDECK_SKIP_ENV_GENERATION:-}" ]; then
      "$(dirname "$0")/generate-env.sh" "${app}"
    fi

    set -a
    source "./apps/${app}/.env"
    set +a

    mkdir -p "./apps-data/${app}"

    config_template_dir="./apps/${app}/config"
    config_dir="./apps-data/${app}/config"

    if [[ -d "$config_template_dir" ]]; then
      mkdir -p "$config_dir"
      for template in "$config_template_dir"/*.template.*; do
        [[ -e "$template" ]] || continue
        filename="$(basename "$template")"
        filename="${filename/.template./.}"
        envsubst < "$template" > "$config_dir/$filename"
        echo "Generated: $config_dir/$filename"
      done
    fi

    docker compose -f "./apps/${app}/docker-compose.yml" pull
    docker compose -f "./apps/${app}/docker-compose.yml" up -d --remove-orphans
  )
done

docker container prune -f
docker image prune -a -f
