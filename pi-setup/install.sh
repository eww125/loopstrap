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

echo "done."
echo "run the controller:  .venv/bin/python controller/looper.py"
echo "hardware test mode:  .venv/bin/python controller/looper.py --mock"
