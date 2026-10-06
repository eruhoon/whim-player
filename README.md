# Whim Player (SMB Media Player for ROCKNIX)

![Version](https://img.shields.io/badge/version-0.1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-ROCKNIX%20%7C%20Linux%20ARM64-orange.svg)

A lightweight Curses-based media player designed for ROCKNIX handheld devices (Linux ARM64 / Rockchip).  
Stream and enjoy high-definition videos directly from your local NAS or router SMB share without local storage constraints.

---

## 🚀 Key Features

* **EmulationStation [Ports] Integration**: Launch directly from the Ports menu on your handheld device.
* **Lossless FUSE (rclone) SMB Mount**: Non-blocking folder browsing and instant video playback streaming.
* **Hardware Accelerated 1080p Playback (`mpv`)**: Smooth 1080p / 4K video decoding via hardware video acceleration (Rockchip MPP).
* **Wayland & Foot Terminal Optimized**: Native Curses UI fine-tuned for high-DPI displays with multi-byte character alignment.
* **Full Gamepad Navigation (`gptokeyb`)**:
  * **File Browser Mode**:
    * `D-Pad Up / Down`: Navigate items
    * `L1 / R1`: Page scroll up / down
    * `A`: Play media / Enter directory
    * `B`: Go up one directory / Back
    * `Y`: Toggle sorting order (Alphabetical / Newest)
    * `Select` or `F`: Toggle favorites (★)
    * `X`: SMB connection settings & mount test
    * `Start` or `Q`: Exit player dialog
  * **Playback Mode (`mpv`)**:
    * `D-Pad Left / Right`: Seek 10 seconds backward / forward
    * `L1 / R1`: Seek 60 seconds backward / forward
    * `D-Pad Up / Down`: Adjust volume
    * `A` / `Start`: Play / Pause toggle
    * `X`: Cycle subtitle tracks
    * `Y`: Cycle audio tracks
    * `B` / `Select`: Stop playback and return to file list
* **Resume Playback**: Automatically remembers watched positions for continuous playback across sessions.

---

## 📥 Installation (For Device Users)

1. Download the latest `smb-player-rocknix.zip` from the [Releases](https://github.com/eruhoon/whim-player/releases) page.
2. Extract the files into your SD card's Ports directory:
   ```text
   /storage/roms/ports/
   ├── SMB Media Player.sh
   └── smb-player/
       ├── main.py
       ├── run_player.sh
       ├── smb_mount.sh
       ├── input.conf
       ├── smb.gptk
       └── config.json
   ```
3. Edit `smb-player/config.json` with your SMB server credentials (or configure directly on the device by pressing `X`).
4. Select and launch **SMB Media Player** from your device's **Ports** menu.

---

## ⚙️ Configuration (`config.json`)

You can create `config.json` by copying `config.example.json`:

```json
{
  "smb_host": "192.168.0.1",
  "smb_port": 445,
  "smb_share": "share",
  "smb_user": "username",
  "smb_pass": "password",
  "mount_point": "/storage/smb_player_mount"
}
```

* **On-device Configuration**: Press `X` in the browser view to open the built-in Virtual Keyboard, enter credentials, and select `[Test Connection & Mount]`.
* **1-Click Remote Deployment**: Deploy updates directly to your device over Wi-Fi using `deploy.sh`:
  ```bash
  ./deploy.sh <DEVICE_IP>
  ```

---

## 🛠️ Development & Build (`pnpm`)

This project uses Node.js and `pnpm` for validation and distribution packaging.

### Prerequisites
* Node.js >= 18
* pnpm

### Commands

```bash
# Install dependencies
pnpm install

# Run automated validation tests (rule checks, sensitive data leak prevention)
pnpm test

# Build distribution artifacts and release ZIP in dist/
pnpm run build

# Deploy to ROCKNIX device via Wi-Fi SSH
pnpm run deploy <DEVICE_IP>
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
