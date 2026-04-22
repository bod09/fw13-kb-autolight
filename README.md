# fw13-kb-autolight

Automatic keyboard backlight control for the Framework Laptop 13 on Fedora Linux.

Keeps the keyboard backlight **off** by default and turns it on to a low brightness when the room gets dark, using the laptop's built-in ambient light sensor. Uses hysteresis (two thresholds) to prevent flickering when ambient light is near the boundary.

## How it works

The daemon polls the ambient light sensor and controls the keyboard backlight via `brightnessctl`:

```
                    raw <= 0 (dark)
  [BRIGHT / OFF] ──────────────────► [DARK / ON at 1%]
                 ◄──────────────────
                    raw > 2 (light)
```

The gap between the two thresholds (0 and 2 by default) is the hysteresis zone — it prevents the backlight from rapidly toggling when ambient light hovers near a single value.

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
light = 2       # Sensor value above which backlight turns OFF

[backlight]
brightness = 1  # Backlight brightness (0-100) when dark
device =        # Leave blank for auto-detect, or set device name

[polling]
interval = 2    # Seconds between sensor reads

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

Set `dark` just above your "covered/dark" reading and `light` well above `dark` to create a comfortable hysteresis gap.

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

```bash
cd fw13-kb-autolight
./uninstall.sh
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

### Service won't start after reboot

By default, systemd user services only run while you are logged in. To keep the service running after logout:

```bash
loginctl enable-linger $USER
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
