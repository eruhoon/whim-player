#!/bin/bash
# ========================================================
# smb_mount.sh - SMB Mount Helper for ROCKNIX & rclone
# ========================================================

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${BASE_DIR}/config.json"
LOG_FILE="/var/log/smb_player_mount.log"

# Ensure fusermount3 compatibility symlink exists
BIN_DIR="/storage/.bin"
mkdir -p "$BIN_DIR"
if [ ! -f "$BIN_DIR/fusermount3" ] && [ -f "/usr/bin/fusermount" ]; then
    ln -sf /usr/bin/fusermount "$BIN_DIR/fusermount3"
fi
export PATH="$BIN_DIR:$PATH"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Parse JSON using python3
SMB_HOST=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('smb_host', '192.168.0.1'))")
SMB_PORT=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('smb_port', 445))")
SMB_SHARE=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('smb_share', 'HDD1'))")
SMB_USER=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('smb_user', ''))")
SMB_PASS=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('smb_pass', ''))")
MOUNT_POINT=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('mount_point', '/storage/smb_player_mount'))")

unmount_share() {
    echo "Unmounting $MOUNT_POINT..."
    fusermount -u "$MOUNT_POINT" 2>/dev/null || umount "$MOUNT_POINT" 2>/dev/null
    sleep 0.5
}

case "$1" in
    unmount)
        unmount_share
        exit 0
        ;;
    status)
        if mountpoint -q "$MOUNT_POINT"; then
            echo "MOUNTED: $MOUNT_POINT"
            exit 0
        else
            echo "NOT_MOUNTED"
            exit 1
        fi
        ;;
    mount|"")
        ;;
    *)
        echo "Usage: $0 [mount|unmount|status]"
        exit 1
        ;;
esac

# Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    echo "Already mounted at $MOUNT_POINT"
    exit 0
fi

# Prepare mount directory
mkdir -p "$MOUNT_POINT"

echo "Mounting //${SMB_HOST}:${SMB_PORT}/${SMB_SHARE} to ${MOUNT_POINT}..."

# Export rclone backend options via environment variables
export RCLONE_SMB_HOST="$SMB_HOST"
export RCLONE_SMB_PORT="$SMB_PORT"

if [ -n "$SMB_USER" ]; then
    export RCLONE_SMB_USER="$SMB_USER"
else
    unset RCLONE_SMB_USER
fi

if [ -n "$SMB_PASS" ]; then
    export RCLONE_SMB_PASS=$(rclone obscure "$SMB_PASS")
else
    unset RCLONE_SMB_PASS
fi

# Execute rclone mount in daemon mode using environment variables
rclone mount :smb:"$SMB_SHARE" "$MOUNT_POINT" \
    --daemon \
    --vfs-cache-mode minimal \
    --read-only \
    --dir-cache-time 60s \
    --no-modtime \
    --log-file "$LOG_FILE" \
    --log-level NOTICE

# Wait up to 5 seconds for mount verification
SUCCESS=0
for i in {1..10}; do
    if mountpoint -q "$MOUNT_POINT"; then
        SUCCESS=1
        break
    fi
    sleep 0.5
done

if [ $SUCCESS -eq 1 ]; then
    echo "SUCCESS: Mounted successfully at $MOUNT_POINT"
    exit 0
else
    echo "ERROR: Mount failed. Last log entries:"
    tail -n 5 "$LOG_FILE" 2>/dev/null
    exit 1
fi
