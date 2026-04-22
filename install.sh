#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_NAME="fw13-kb-autolight"

BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/$DAEMON_NAME"
SERVICE_DIR="$HOME/.config/systemd/user"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Preflight checks ---

info "Running preflight checks..."

# Python 3
if ! command -v python3 &>/dev/null; then
    error "Python 3 is required but not found. Install it with: sudo dnf install python3"
    exit 1
fi
info "Python 3 found: $(python3 --version)"

# ectool
if ! command -v ectool &>/dev/null; then
    error "ectool is not installed."
    echo ""
    echo "  Install via COPR (recommended):"
    echo "    sudo dnf copr enable dustymabe/ectool"
    echo "    sudo dnf install ectool"
    echo ""
    echo "  Or build from source:"
    echo "    https://github.com/FrameworkComputer/ectool"
    echo ""
    exit 1
fi
info "ectool found: $(command -v ectool)"

# Test ectool communication
if ! ectool pwmgetkblight &>/dev/null; then
    warn "ectool cannot communicate with the EC."
    echo "  You may need a udev rule to grant your user access to /dev/cros_ec."
    echo "  See the README for instructions."
    echo ""
    echo "  Continuing installation anyway — fix permissions before starting the service."
fi

# Ambient light sensor
SENSOR_MATCHES=$(find /sys/bus/iio/devices/iio:device*/in_illuminance_raw 2>/dev/null || true)
if [ -z "$SENSOR_MATCHES" ]; then
    warn "No ambient light sensor found."
    echo "  Expected at: /sys/bus/iio/devices/iio:device*/in_illuminance_raw"
    echo "  Try loading the kernel module: sudo modprobe hid_sensor_als"
    echo ""
    echo "  Continuing installation anyway — the service will fail until the sensor is available."
else
    info "Ambient light sensor found: $(echo "$SENSOR_MATCHES" | head -1)"
fi

# --- Install ---

info "Installing daemon script to $BIN_DIR/"
mkdir -p "$BIN_DIR"
cp "$SCRIPT_DIR/$DAEMON_NAME.py" "$BIN_DIR/$DAEMON_NAME.py"
chmod +x "$BIN_DIR/$DAEMON_NAME.py"

if [ -f "$CONFIG_DIR/$DAEMON_NAME.conf" ]; then
    info "Config file already exists at $CONFIG_DIR/$DAEMON_NAME.conf — keeping existing config"
else
    info "Installing default config to $CONFIG_DIR/"
    mkdir -p "$CONFIG_DIR"
    cp "$SCRIPT_DIR/$DAEMON_NAME.conf" "$CONFIG_DIR/$DAEMON_NAME.conf"
fi

info "Installing systemd user service to $SERVICE_DIR/"
mkdir -p "$SERVICE_DIR"
cp "$SCRIPT_DIR/$DAEMON_NAME.service" "$SERVICE_DIR/$DAEMON_NAME.service"

info "Reloading systemd user daemon..."
systemctl --user daemon-reload

info "Enabling and starting $DAEMON_NAME service..."
systemctl --user enable --now "$DAEMON_NAME.service"

echo ""
info "Installation complete!"
echo ""
systemctl --user status "$DAEMON_NAME.service" --no-pager || true
echo ""
echo "  View logs:     journalctl --user -u $DAEMON_NAME -f"
echo "  Edit config:   $CONFIG_DIR/$DAEMON_NAME.conf"
echo "  Restart:       systemctl --user restart $DAEMON_NAME"
echo ""

# Linger check
LINGER=$(loginctl show-user "$USER" -p Linger 2>/dev/null | cut -d= -f2 || echo "unknown")
if [ "$LINGER" != "yes" ]; then
    warn "Linger is not enabled for your user."
    echo "  The service will only run while you are logged in."
    echo "  To enable linger (service runs even when logged out):"
    echo "    loginctl enable-linger $USER"
    echo ""
fi
