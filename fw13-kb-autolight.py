#!/usr/bin/env python3
"""
fw13-kb-autolight — Automatic keyboard backlight control for Framework Laptop 13.

Reads the ambient light sensor and toggles the keyboard backlight via ectool.
Uses hysteresis (two thresholds) to avoid flickering near the boundary.
"""

import configparser
import glob
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# Built-in defaults (used if config file is missing or incomplete)
DEFAULTS = {
    "dark": 20,
    "light": 40,
    "brightness": 1,
    "interval": 2,
    "device": "",
}

CONFIG_PATH = os.path.expanduser("~/.config/fw13-kb-autolight/fw13-kb-autolight.conf")
SENSOR_GLOB = "/sys/bus/iio/devices/iio:device*/in_illuminance_raw"

running = True


def handle_signal(signum, frame):
    global running
    running = False


def load_config():
    config = configparser.ConfigParser()

    if os.path.isfile(CONFIG_PATH):
        config.read(CONFIG_PATH)
        logging.info("Loaded config from %s", CONFIG_PATH)
    else:
        logging.info("No config file found at %s, using defaults", CONFIG_PATH)

    dark = config.getint("thresholds", "dark", fallback=DEFAULTS["dark"])
    light = config.getint("thresholds", "light", fallback=DEFAULTS["light"])
    brightness = config.getint("backlight", "brightness", fallback=DEFAULTS["brightness"])
    interval = config.getint("polling", "interval", fallback=DEFAULTS["interval"])
    device = config.get("sensor", "device", fallback=DEFAULTS["device"]).strip()

    if dark >= light:
        logging.error(
            "Invalid config: dark threshold (%d) must be less than light threshold (%d)",
            dark, light,
        )
        sys.exit(1)

    if not 0 <= brightness <= 100:
        logging.error("Invalid config: brightness (%d) must be between 0 and 100", brightness)
        sys.exit(1)

    if interval < 1:
        logging.error("Invalid config: poll interval (%d) must be at least 1 second", interval)
        sys.exit(1)

    return dark, light, brightness, interval, device


def find_sensor(device_override):
    if device_override:
        if os.path.isfile(device_override):
            logging.info("Using configured sensor: %s", device_override)
            return device_override
        else:
            logging.error("Configured sensor path does not exist: %s", device_override)
            sys.exit(1)

    matches = sorted(glob.glob(SENSOR_GLOB))
    if not matches:
        logging.error(
            "No ambient light sensor found at %s. "
            "Check that the sensor kernel module is loaded (try: modprobe hid_sensor_als).",
            SENSOR_GLOB,
        )
        sys.exit(1)

    sensor = matches[0]
    logging.info("Auto-detected sensor: %s", sensor)
    if len(matches) > 1:
        logging.info(
            "Multiple sensors found (%d total). Using the first one. "
            "Set 'device' in the config file to override.",
            len(matches),
        )
    return sensor


def check_ectool():
    if not shutil.which("ectool"):
        logging.error(
            "ectool not found on PATH. Install it first:\n"
            "  Via fw-fanctrl: https://github.com/TamtamHero/fw-fanctrl\n"
            "  Via COPR: sudo dnf copr enable bsvh/fw-ectool && sudo dnf install fw-ectool\n"
            "  Build from source: https://gitlab.howett.net/DHowett/ectool"
        )
        sys.exit(1)

    # Test that ectool can actually communicate with the EC
    try:
        subprocess.run(
            ["ectool", "pwmgetkblight"],
            check=True, capture_output=True, timeout=5,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode().strip()
        logging.error(
            "ectool cannot communicate with the EC: %s\n"
            "You may need a udev rule to grant access to /dev/cros_ec. See the README.",
            stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logging.error("ectool timed out communicating with the EC.")
        sys.exit(1)


def set_backlight(value):
    try:
        subprocess.run(
            ["ectool", "pwmsetkblight", str(value)],
            check=True, capture_output=True, timeout=5,
        )
    except subprocess.CalledProcessError as e:
        logging.error("ectool pwmsetkblight failed: %s", e.stderr.decode().strip())
    except subprocess.TimeoutExpired:
        logging.error("ectool pwmsetkblight timed out")


def read_sensor(sensor_path):
    try:
        return int(Path(sensor_path).read_text().strip())
    except (OSError, ValueError) as e:
        logging.warning("Failed to read sensor: %s", e)
        return None


def main():
    global running

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    dark, light, brightness, interval, device_override = load_config()
    sensor_path = find_sensor(device_override)
    check_ectool()

    logging.info(
        "Starting: dark=%d, light=%d, brightness=%d%%, poll=%ds",
        dark, light, brightness, interval,
    )

    # Start with backlight off
    state = "bright"
    set_backlight(0)

    while running:
        raw = read_sensor(sensor_path)
        if raw is None:
            time.sleep(interval)
            continue

        if state == "bright" and raw < dark:
            set_backlight(brightness)
            state = "dark"
            logging.info("Dark detected (raw=%d < %d), backlight ON at %d%%", raw, dark, brightness)
        elif state == "dark" and raw > light:
            set_backlight(0)
            state = "bright"
            logging.info("Light detected (raw=%d > %d), backlight OFF", raw, light)

        time.sleep(interval)

    # Clean shutdown
    set_backlight(0)
    logging.info("Shutting down, backlight off")


if __name__ == "__main__":
    main()
