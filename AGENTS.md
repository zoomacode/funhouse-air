# AGENTS.md

Notes for AI coding assistants working on this repo. The project is a
desktop weather station running on an **Adafruit FunHouse** (ESP32-S2)
with **CircuitPython 10.x**. External I²C sensors:

- **BME680** at I²C `0x76` — temperature / humidity / pressure / gas
- **PMSA003** (`adafruit_pm25.i2c`) at `0x12` — particulate matter

## Quick map

```
code.py                  Orchestrator: imports + main loop
components/config.py     ALL user-tunable settings (font scales, colors,
                         timings, comfort thresholds, MQTT topic, PIR pin)
components/sensors.py    BME680 + PMSA003 wrapper, AQI / heat-index /
                         dewpoint / comfort-score derivation
components/state.py      Rolling history buffer (used for sparkline +
                         trend arrows). Capacity comes from config.
components/ui.py         displayio UI: status bar, vertical hint column
                         on the left, three screens (Now / Air / Trend)
deploy.sh                Copy code.py + components/ to /Volumes/CIRCUITPY,
                         optional --reload (Ctrl-D over serial) and
                         --tail to watch boot output
install-libs.sh          rsync libs from a CP bundle into /Volumes/
                         CIRCUITPY/lib (uses lib-requirements.txt)
lib-requirements.txt     List of CP libraries this project needs
settings.toml            (gitignored) WiFi + MQTT credentials. Keys are
                         CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD,
                         MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_KEY
```

## Default workflow

1. **Edit** `code.py`, `components/*.py`, or `components/config.py`.
2. **Deploy**: `./deploy.sh --reload --tail` (the tail prints boot output
   for 10 s — long enough to catch a Traceback).
3. **Verify** via screen photo or by tailing serial. The user has Mu
   Editor connected to the REPL most of the time, so the same prints
   that appear on serial also show in Mu's bottom pane.

## Editing rules of thumb

- **Tunables go in `components/config.py`**, not as constants in
  `code.py` or `ui.py`. The user often wants to tweak font scales /
  thresholds / timings without reading code.
- **Layout positions in `ui.py` are scale-dependent.** When changing a
  font scale, also re-verify the y-coordinates around it (rows in
  NowScreen are tight). The `SHOW_FEELS` toggle has two pre-tuned
  layouts (with and without the "feels" line).
- **Don't put credentials anywhere but `settings.toml`** (which is
  gitignored). Avoid printing them.
- **Keep the main loop non-blocking.** `time.sleep` for ≥100 ms blocks
  buttons and PIR. Loop sleep is set to 15 ms.
- **PIRs latch HIGH for several seconds.** Always use rising-edge
  detection (level polling pins the wake timer).

## Common screens / hardware quirks

- **`code.py output:` and nothing more on screen** = code.py is hanging
  during init (or imports). Use the *incremental import probe* below.
- **Mu shows no output, REPL won't accept input** = the device's USB
  CDC channel is wedged. Unplug-replug the USB cable; if that doesn't
  fix it, reset the device.
- **CIRCUITPY drive disappears after a deploy** = the device hard-faulted.
  Reset it.
- **Filesystem entries with garbage names** (e.g. `METAÜ÷ÿ?`,
  `WIFI\x01\x10␀À.MPY`, `ADAFÜ÷ÿ?.MPY`) appear after stress: copies that
  collide with macOS xattrs on FAT can corrupt the directory entry.
  - Standard tools (rm, mv, ls) cannot remove these because the dirent
    exists but the file doesn't resolve.
  - First-line workaround: `rm -rf` the parent directory (sometimes
    succeeds when the phantom is mid-directory) and copy fresh from
    the bundle. Failing that, rename the parent dir aside (`mv X X_OLD`)
    and put a clean copy alongside.
  - Last resort: drop a `boot.py` containing
    `import storage; storage.erase_filesystem()` and reset the device.
    On the next boot CP wipes the user filesystem clean. (This only
    works if CP is not in safe mode. In safe mode you need ROM-bootloader
    + esptool erase_flash.)

## Incremental import probe

When `code.py` hangs silently and you can't tell which import is to
blame, replace `code.py` with a probe that prints between imports:

```python
import time
print("=== probe ===")
print("1: stdlib"); import os, sys, json
print("2: board");  import board
print("3: wifi");   import wifi
print("4: funhouse"); from adafruit_funhouse import FunHouse
print("5: components"); from components.sensors import Sensors
print("ALL OK")
i = 0
while True:
    print("tick", i); i += 1; time.sleep(2)
```

The last printed number tells you which import hung. Add finer-grained
probes inside the offending package's submodules to narrow further.

## Deploy / recover cheatsheet

| Situation                                         | Action |
| ------------------------------------------------- | --- |
| Edited `code.py` or `components/*`                | `./deploy.sh --reload --tail` |
| Need fresh libraries (after firmware reflash)     | `./install-libs.sh` |
| Filesystem corruption (phantom files)             | `boot.py` with `storage.erase_filesystem()` + reset |
| Filesystem corruption + safe mode                 | UF2 bootloader → drag UF2 → if still bad, ROM bootloader → `esptool erase_flash` → drag UF2 → `./install-libs.sh` → `./deploy.sh` → restore `settings.toml` |
| Want to reflash CP firmware only                  | Slow double-click reset → wait for purple LED → press reset → drag UF2 onto `HOUSEBOOT` |
| Need ROM bootloader (full chip access)            | Hold BOOT/DFU, press RESET, release BOOT |

## Constraints CP will hold you to

- **Modules are .mpy versioned.** A bundle compiled for CP 9 will not
  load on CP 10. Always pull from the bundle matching the CP major
  version on `boot_out.txt`.
- **Filesystem is read-only from CP at runtime by default** so the USB
  host can write. To make it writable from CP (e.g. for screenshots
  via `adafruit_bitmapsaver`), you'd need `storage.remount("/", readonly=False)`
  in `boot.py`, which then makes the USB drive read-only on the host.
  We avoid this; the screenshot helper instead streams base64 over
  serial.
- **GPIO0 (D0) is a strap pin.** Wiring an external sensor's OUT to D0
  prevents boot when the sensor pulls it LOW. Use A0 (GPIO16) — it is
  the default for `EXTERNAL_PIR_PIN` in `config.py`.
- **`funhouse.splash` is deprecated** in CP 10. Use
  `funhouse.display.root_group = group` instead. The library itself
  still emits a deprecation warning; can't be silenced from user code.

## What the device looks like when working

- Status bar (top): `1/3 NOW` + green `MQTT` + green `WiFi` indicators.
- Left strip: ▲ Trend, S F/C, ▼ Air (for the Now screen — labels change
  per screen).
- Big temp + comfort indicators on humidity / pressure rows.
- AQI band at the bottom in green / amber / red depending on PM2.5.
- Dotstars off when AQI is good; ramp yellow → red as it worsens.
- Display dims after 30 s idle, sleeps after 3 min idle. PIR or any
  button wakes it.
