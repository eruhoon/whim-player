#!/bin/bash
# ========================================================
# deploy.sh - Deploy to Ports (/storage/roms/ports)
# ========================================================

DEVICE_IP="${1:-192.168.0.77}"
REMOTE_USER="root"
REMOTE_PORTS_DIR="/storage/roms/ports"
REMOTE_APP_DIR="${REMOTE_PORTS_DIR}/smb-player"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Deploying smb-player to Ports on (${DEVICE_IP})..."

# 1. Test SSH Connection
if ! ssh -o ConnectTimeout=3 -o BatchMode=yes "${REMOTE_USER}@${DEVICE_IP}" "true" 2>/dev/null; then
    echo "ERROR: Cannot connect to ${DEVICE_IP} via SSH."
    exit 1
fi

# 2. Clean old system module location if present
ssh "${REMOTE_USER}@${DEVICE_IP}" "rm -rf /storage/.config/modules/smb-player /storage/.config/modules/smb-player.sh" 2>/dev/null

# 3. Create remote directory
ssh "${REMOTE_USER}@${DEVICE_IP}" "mkdir -p '${REMOTE_APP_DIR}'"

# 4. Copy files
echo "==> Copying app files..."
scp "${BASE_DIR}/main.py" \
    "${BASE_DIR}/config.json" \
    "${BASE_DIR}/input.conf" \
    "${BASE_DIR}/smb.gptk" \
    "${BASE_DIR}/smb_mount.sh" \
    "${BASE_DIR}/run_player.sh" \
    "${REMOTE_USER}@${DEVICE_IP}:${REMOTE_APP_DIR}/"

scp "${BASE_DIR}/smb-player.sh" \
    "${REMOTE_USER}@${DEVICE_IP}:${REMOTE_PORTS_DIR}/SMB Media Player.sh"

# 5. Set execution permissions
echo "==> Setting permissions..."
ssh "${REMOTE_USER}@${DEVICE_IP}" "chmod +x '${REMOTE_PORTS_DIR}/SMB Media Player.sh' '${REMOTE_APP_DIR}/main.py' '${REMOTE_APP_DIR}/run_player.sh' '${REMOTE_APP_DIR}/smb_mount.sh'"

echo "==> Deployment completed successfully!"
echo "    Ports 메뉴에서 'SMB Media Player'를 실행하세요."
