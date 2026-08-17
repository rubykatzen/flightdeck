#!/bin/bash

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <server-address>"
  exit 1
fi

SERVER="$1"
REMOTE_APPS_DATA="~/flightdeck/apps-data"
REMOTE_PROJECT="~/flightdeck"
LOCAL_BACKUPS_DIR="$(dirname "$0")/backups"
DATETIME=$(date +"%Y%m%d_%H%M%S")
SERVER_NAME=$(echo "$SERVER" | sed 's/[^a-zA-Z0-9]/_/g')

mkdir -p "$LOCAL_BACKUPS_DIR"

echo "==> Getting list of app directories..."
APPS=$(ssh "$SERVER" "ls -d $REMOTE_APPS_DATA/*/  2>/dev/null | xargs -I{} basename {}")

if [ -z "$APPS" ]; then
  echo "No app directories found in $REMOTE_APPS_DATA"
  exit 0
fi

echo "==> Reading APPS from remote .env..."
APPS_LIST=$(ssh "$SERVER" "bash -c 'source $REMOTE_PROJECT/.env && echo \"\${APPS//,/ }\"'")

echo "==> Found apps: $(echo "$APPS" | tr '\n' ' ')"
echo "==> Active APPS: $APPS_LIST"

REMOTE_TMP="/tmp/flightdeck-backup-$$"
ssh "$SERVER" "mkdir -p $REMOTE_TMP"

for APP in $APPS; do
  ARCHIVE="${APP}-${DATETIME}-${SERVER_NAME}.zip"
  echo ""
  if echo " $APPS_LIST " | grep -qw "$APP"; then
    echo "==> [$APP] Stopping container..."
    ssh "$SERVER" "cd $REMOTE_PROJECT && ./down.sh $APP" > /dev/null 2>&1
    echo "==> [$APP] Creating zip archive..."
    ssh "$SERVER" "cd $REMOTE_APPS_DATA && find $APP/ -not -type s | zip $REMOTE_TMP/$ARCHIVE -@ -q"
    echo "==> [$APP] Starting container back..."
    ssh "$SERVER" "cd $REMOTE_PROJECT && ./up.sh $APP" > /dev/null 2>&1
  else
    echo "==> [$APP] Not in APPS, skipping stop/start..."
    ssh "$SERVER" "cd $REMOTE_APPS_DATA && find $APP/ -not -type s | zip $REMOTE_TMP/$ARCHIVE -@ -q"
  fi
  echo "==> [$APP] Downloading archive..."
  scp "$SERVER:$REMOTE_TMP/$ARCHIVE" "$LOCAL_BACKUPS_DIR/$ARCHIVE"
  ssh "$SERVER" "rm -f $REMOTE_TMP/$ARCHIVE"
  echo "==> [$APP] Done."
done

ssh "$SERVER" "rm -rf $REMOTE_TMP"

echo ""
echo "Backup complete. Files saved to: $LOCAL_BACKUPS_DIR"
ls -lh "$LOCAL_BACKUPS_DIR/"*"-${DATETIME}-${SERVER_NAME}.zip" 2>/dev/null || true
