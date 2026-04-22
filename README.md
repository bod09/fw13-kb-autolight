# fw13-kb-autolight

Automatic keyboard backlight control for the Framework Laptop 13 on Fedora Linux.

Keeps the keyboard backlight **off** by default and turns it on to a low brightness when the room gets dark, using the laptop's built-in ambient light sensor. Turns on instantly in the dark and uses debounce when turning off to prevent flickering.

## How it works

The daemon polls the ambient light sensor and controls the keyboard backlight via `brightnessctl`:

```
                    raw <= 0 (instant)
  [BRIGHT / OFF] ──────────────────────────────────────► [DARK / ON at 1%]
                 ◄──────────────────────────────────────
                    raw > 1 (3 consecutive readings)
```

Turning **on** is instant — when it goes dark you need to see the keys now. Turning **off** is debounced (default: 3 consecutive readings) to prevent flickering from brief sensor fluctuations.

## Prerequisites

- **Framework Laptop 13** (Intel or AMD) with an ambient light sensor
- **Fedora 41+** (other distros should work but are untested)
- **Python 3** (included with Fedora)
- **brightnessctl** — controls the keyboard backlight without root

### Installing brightnessctl

```bash
sudo dnf install brightnessctl
```

## Installation

```bash
curl -L https://github.com/bod09/fw13-kb-autolight/archive/refs/heads/main.tar.gz | tar xz
cd fw13-kb-autolight-main
./install.sh
```

Or if you have git installed:

```bash
git clone https://github.com/bod09/fw13-kb-autolight.git
cd fw13-kb-autolight
./install.sh
```

The install script will:
1. Check for Python 3, brightnessctl, keyboard backlight, and the ambient light sensor
2. Install the daemon to `~/.local/bin/`
3. Install the default config to `~/.config/fw13-kb-autolight/`
4. Install and start a systemd user service (no root needed)

## Configuration

Edit `~/.config/fw13-kb-autolight/fw13-kb-autolight.conf`:

```ini
[thresholds]
dark = 0        # Sensor value at or below which backlight turns ON
light = 1       # Sensor value above which backlight turns OFF

[backlight]
brightness = 1  # Backlight brightness (0-100) when dark
device =        # Leave blank for auto-detect, or set device name

[polling]
interval = 1    # Seconds between sensor reads
debounce = 3    # Consecutive readings needed before switching

[sensor]
device =        # Leave blank for auto-detect, or set full sysfs path
```

After editing, restart the service:

```bash
systemctl --user restart fw13-kb-autolight
```

### Finding your sensor values

Read the raw sensor value to calibrate your thresholds:

```bash
# Find your sensor
ls /sys/bus/iio/devices/iio:device*/in_illuminance_raw

# Read the current value
cat /sys/bus/iio/devices/iio:device0/in_illuminance_raw
```

Try reading the value in different lighting conditions:
- Cover the sensor with your hand — note the low value
- Normal room lighting — note the value
- Bright daylight — note the high value

Set `dark` to the value where you can no longer comfortably see the keys, and `light` to the value where you can.

### Finding your keyboard backlight device

```bash
ls /sys/class/leds/*kbd_backlight
```

Common device names:
- `chromeos::kbd_backlight` — most Framework 13 models
- `framework_laptop::kbd_backlight` — with the framework-laptop-kmod kernel module

The daemon auto-detects this, but you can pin it in the config under `[backlight] device`.

## Usage

```bash
# Check service status
systemctl --user status fw13-kb-autolight

# View live logs
journalctl --user -u fw13-kb-autolight -f

# Restart after config changes
systemctl --user restart fw13-kb-autolight

# Stop temporarily
systemctl --user stop fw13-kb-autolight

# Start again
systemctl --user start fw13-kb-autolight
```

## Uninstallation

If you still have the source folder:

```bash
cd fw13-kb-autolight-main
./uninstall.sh
```

Or re-download and uninstall:

```bash
curl -L https://github.com/bod09/fw13-kb-autolight/archive/refs/heads/main.tar.gz | tar xz
./fw13-kb-autolight-main/uninstall.sh
```

This stops the service, removes the daemon and service file, and optionally removes the config directory.

## Troubleshooting

### Sensor not found

If the install script or daemon reports no sensor:

```bash
# Check if the kernel module is loaded
lsmod | grep hid_sensor_als

# Load it manually
sudo modprobe hid_sensor_als

# Make it persistent
echo "hid_sensor_als" | sudo tee /etc/modules-load.d/hid_sensor_als.conf
```

### KDE Plasma conflict

KDE's Powerdevil may also try to manage the keyboard backlight. To avoid conflicts, disable KDE's keyboard backlight control:

**System Settings → Power Management → Keyboard Brightness** — uncheck automatic adjustment or set it to manual.

### Service keeps restarting

Check the logs for errors:

```bash
journalctl --user -u fw13-kb-autolight --no-pager -n 50
```

Common causes:
- Sensor path changed after a kernel update (restart the service to re-detect)
- Invalid config values (dark must be less than light)

## License

MIT — see [LICENSE](LICENSE).
