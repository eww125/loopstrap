#!/bin/bash
# One-time setup on the Raspberry Pi Zero 2 W.
# Run from the repo root:  bash pi-setup/install.sh
set -e
cd "$(dirname "$0")/.."

sudo apt update
sudo apt install -y git python3-venv python3-dev

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -r controller/requirements.txt

# Auto-update: the Pi pulls the latest code from GitHub on every boot.
sudo cp pi-setup/loopstrap-update.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable loopstrap-update.service

# Controller service: runs the looper at boot, restarts on crash, logs output.
sudo cp pi-setup/loopstrap.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now loopstrap.service

echo "done."
echo "live log:   journalctl -u loopstrap -f"
echo "restart:    sudo systemctl restart loopstrap"
echo "manual run: .venv/bin/python controller/looper.py"
