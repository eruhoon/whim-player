#!/bin/bash
source /etc/profile
export TERM=linux
export LANG=ko_KR.UTF-8
export LC_ALL=ko_KR.UTF-8

cd "$(dirname "$0")"

# Run gptokeyb inside foot terminal session
if command -v gptokeyb >/dev/null 2>&1; then
    gptokeyb python3 -c ./smb.gptk &
    GP_PID=$!
fi

python3 ./main.py

if [ -n "$GP_PID" ]; then
    kill -9 "$GP_PID" 2>/dev/null
fi
killall -9 gptokeyb 2>/dev/null

./smb_mount.sh unmount >/dev/null 2>&1
