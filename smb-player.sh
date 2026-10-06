#!/bin/bash
source /etc/profile

export WAYLAND_DISPLAY="wayland-1"
export XDG_RUNTIME_DIR="/var/run/0-runtime-dir"

SOCK=$(ls /var/run/0-runtime-dir/sway-ipc.*.sock 2>/dev/null | head -n 1)
if [ -n "$SOCK" ]; then
    export SWAYSOCK="$SOCK"
    swaymsg 'for_window [app_id="smb-player"] fullscreen enable' >/dev/null 2>&1
    swaymsg 'for_window [app_id="mpv"] fullscreen enable' >/dev/null 2>&1
fi

APP_DIR="$(cd "$(dirname "$0")/smb-player" && pwd)"
cd "$APP_DIR" || exit 1

foot -t linux -F -a smb-player "$APP_DIR/run_player.sh"
