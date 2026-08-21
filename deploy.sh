#!/bin/bash
set -e
source "$(dirname "$0")/lib.sh"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ $# -gt 0 ]; then
  apps=("$@")
else
  parse_apps "$APPS"
fi

if [ -z "${FLIGHTDECK_SKIP_ENV_GENERATION:-}" ]; then
  "$(dirname "$0")/generate-env.sh" "${apps[@]}"
fi

for app in "${apps[@]}"; do
  require_app_compose "${app}"
  if grep -q 'com.centurylinklabs.watchtower.enable=true' "./apps/${app}/docker-compose.yml" 2>/dev/null; then
    echo "Skipping restart: ${app} (managed by Watchtower, env regenerated)"
    continue
  fi
  "$(dirname "$0")/restart.sh" "$app"
done
