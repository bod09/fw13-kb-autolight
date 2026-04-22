# fw13-kb-autolight

Automatic keyboard backlight control for the Framework Laptop 13 on Fedora Linux.

Keeps the keyboard backlight **off** by default and turns it on to a low brightness when the room gets dark, using the laptop's built-in ambient light sensor. Uses hysteresis (two thresholds) to prevent flickering when ambient light is near the boundary.

## How it works

The daemon polls the ambient light sensor and controls the keyboard backlight via `ectool`:

```
                    raw < 20 (dark)
  [BRIGHT / OFF] ──────────────────► [DARK / ON at 1%]
                 ◄──────────────────
                    raw > 40 (light)
```

The gap between the two thresholds (20 and 40 by default) is the hysteresis zone — it prevents the backlight from rapidly toggling when ambient light hovers near a single value.

## Prerequisites

- **Framework Laptop 13** (Intel or AMD) with an ambient light sensor
- **Fedora 41+** (other distros should work but are untested)
- **Python 3** (included with Fedora)
- **ectool** — communicates with the Framework embedded controller

### Installing ectool

Via COPR (recommended):

```bash
sudo dnf copr enable dustymabe/ectool
sudo dnf install ectool
```

Or build from source: [github.com/FrameworkComputer/ectool](https://github.com/FrameworkComputer/ectool)

### ectool permissions

If `ectool pwmgetkblight` fails with a permission error, you need a udev rule to grant your user access to `/dev/cros_ec`.

Create `/etc/udev/rules.d/99-cros-ec.rules`:

```
KERNEL=="cros_ec", SUBSYSTEM=="misc", MODE="0660", GROUP="plugdev"
```

Then add your user to the `plugdev` group and reload:

```bash
sudo usermod -aG plugdev $USER
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Log out and back in for the group change to take effect.

## Installation

```bash
git clone https://github.com/bod09/fw13-kb-autolight.git
cd fw13-kb-autolight
./install.sh
```

The install script will:
1. Check for Python 3, ectool, and the ambient light sensor
2. Install the daemon to `~/.local/bin/`
3. Install the default config to `~/.config/fw13-kb-autolight/`
4. Install and start a systemd user service (no root needed)

## Configuration

Edit `~/.config/fw13-kb-autolight/fw13-kb-autolight.conf`:

```ini
[thresholds]
dark = 20       # Sensor value below which backlight turns ON
light = 40      # Sensor value above which backlight turns OFF

[backlight]
brightness = 1  # Backlight brightness (0-100) when dark

[polling]
interval = 2    # Seconds between sensor reads

[sensor]
device =        # Leave blank for auto-detect, or set full path
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
- Cover the sensor with your hand → note the low value
- Normal room lighting → note the value
- Bright daylight → note the high value

Set `dark` just above your "covered/dark" reading and `light` well above `dark` to create a comfortable hysteresis gap.

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

**System Settings → Power Management → Keyboard Brightness** → uncheck automatic adjustment or set it to manual.

### Service keeps restarting

Check the logs for errors:

```bash
journalctl --user -u fw13-kb-autolight --no-pager -n 50
```

Common causes:
- ectool permission denied (see [ectool permissions](#ectool-permissions))
- Sensor path changed after a kernel update (restart the service to re-detect)
- Invalid config values (dark must be less than light)

## License

MIT — see [LICENSE](LICENSE).
