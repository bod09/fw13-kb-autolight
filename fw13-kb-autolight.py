#!/usr/bin/env python3
"""
fw13-kb-autolight — Automatic keyboard backlight control for Linux laptops.

Reads the ambient light sensor and toggles the keyboard backlight via logind D-Bus.
Uses debounce to avoid flickering when turning off.
"""

import configparser
import glob
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Built-in defaults (used if config file is missing or incomplete)
DEFAULTS = {
    "dark": 0,
    "light": 1,
    "brightness": 1,
    "interval": 1,
    "debounce": 3,
    "sensor": "",
    "keyboard": "",
}

CONFIG_PATH = os.path.expanduser("~/.config/fw13-kb-autolight/fw13-kb-autolight.conf")
SENSOR_GLOB = "/sys/bus/iio/devices/iio:device*/in_illuminance_raw"
KBD_BACKLIGHT_GLOB = "/sys/class/leds/*kbd_backlight"

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
    debounce = config.getint("polling", "debounce", fallback=DEFAULTS["debounce"])
    sensor = config.get("sensor", "device", fallback=DEFAULTS["sensor"]).strip()
    keyboard = config.get("backlight", "device", fallback=DEFAULTS["keyboard"]).strip()

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

    if debounce < 1:
        logging.error("Invalid config: debounce (%d) must be at least 1", debounce)
        sys.exit(1)

    return dark, light, brightness, interval, debounce, sensor, keyboard


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
            "Set 'device' in [sensor] config to override.",
            len(matches),
        )
    return sensor


def find_keyboard(device_override):
    if device_override:
        return device_override

    matches = sorted(glob.glob(KBD_BACKLIGHT_GLOB))
    if not matches:
        logging.error(
            "No keyboard backlight found at %s. "
            "Check that your laptop has a keyboard backlight and the driver is loaded.",
            KBD_BACKLIGHT_GLOB,
        )
        sys.exit(1)

    # Extract device name from path (e.g., "chromeos::kbd_backlight")
    device = os.path.basename(matches[0])
    logging.info("Auto-detected keyboard backlight: %s", device)
    if len(matches) > 1:
        logging.info(
            "Multiple keyboard backlights found (%d total). Using the first one. "
            "Set 'device' in [backlight] config to override.",
            len(matches),
        )
    return device


def get_backlight(device):
    try:
        return int(Path(f"/sys/class/leds/{device}/brightness").read_text().strip())
    except (OSError, ValueError):
        return None


def set_backlight(device, value):
    try:
        subprocess.run(
            [
                "busctl", "call",
                "org.freedesktop.login1",
                "/org/freedesktop/login1/session/auto",
                "org.freedesktop.login1.Session",
                "SetBrightness", "ssu",
                "leds", device, str(value),
            ],
            check=True, capture_output=True, timeout=5,
        )
    except subprocess.CalledProcessError as e:
        logging.error("Failed to set backlight: %s", e.stderr.decode().strip())
    except subprocess.TimeoutExpired:
        logging.error("Failed to set backlight: timed out")


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

    dark, light, brightness, interval, debounce, sensor_override, kbd_override = load_config()
    sensor_path = find_sensor(sensor_override)
    kbd_device = find_keyboard(kbd_override)

    logging.info(
        "Starting: dark=%d, light=%d, brightness=%d%%, poll=%ds, debounce=%d, keyboard=%s",
        dark, light, brightness, interval, debounce, kbd_device,
    )

    # Start with backlight off
    state = "bright"
    set_backlight(kbd_device, 0)
    counter = 0
    last_set = 0

    while running:
        raw = read_sensor(sensor_path)
        if raw is None:
            time.sleep(interval)
            continue

        now = time.monotonic()

        if state == "bright" and raw <= dark:
            # Turn on immediately — you need to see the keys now
            set_backlight(kbd_device, brightness)
            state = "dark"
            counter = 0
            last_set = now
            logging.info("Dark detected (raw=%d <= %d), backlight ON at %d%%", raw, dark, brightness)
        elif state == "dark" and raw > light:
            # Debounce before turning off — avoid flicker
            counter += 1
            if counter >= debounce:
                set_backlight(kbd_device, 0)
                state = "bright"
                counter = 0
                last_set = now
                logging.info("Light detected (raw=%d > %d), backlight OFF", raw, light)
        else:
            counter = 0
            # Recover from suspend/resume — the EC can silently zero the
            # backlight. Check the actual value and only write if wrong.
            if state == "dark" and now - last_set >= 5:
                actual = get_backlight(kbd_device)
                if actual is not None and actual != brightness:
                    set_backlight(kbd_device, brightness)
                    logging.info("Backlight was reset (was %d), restoring to %d%%", actual, brightness)
                last_set = now

        time.sleep(interval)

    # Clean shutdown
    set_backlight(kbd_device, 0)
    logging.info("Shutting down, backlight off")


if __name__ == "__main__":
    main()
