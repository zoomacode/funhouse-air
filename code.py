"""FunHouse weather station: BME680 + PMSA003 + nice UI."""

import os
import sys
import time
import json

import board
import digitalio
import supervisor
import wifi

from adafruit_funhouse import FunHouse

from components import config
from components.sensors import Sensors
from components.state import History
from components.ui import UI, TrendScreen


# Tunables that don't usually need config exposure
DEBOUNCE = 0.06
LOOP_SLEEP = 0.015

# Pull everything else from components/config.py
SENSOR_INTERVAL = config.SENSOR_INTERVAL_SEC
HISTORY_INTERVAL = config.HISTORY_INTERVAL_SEC
MQTT_INTERVAL = config.MQTT_INTERVAL_SEC
DIM_AFTER = config.DIM_AFTER_SEC
SLEEP_AFTER = config.SLEEP_AFTER_SEC
TEMP_OFFSET_C = config.TEMP_OFFSET_C
EXTERNAL_PIR_PIN = config.EXTERNAL_PIR_PIN
PIR_SUSTAIN_SEC = config.PIR_SUSTAIN_SEC
MQTT_TOPIC = config.MQTT_TOPIC


def _env(key, default=None):
    val = os.getenv(key)
    return val if val is not None else default


MQTT_BROKER = _env("MQTT_BROKER")
MQTT_PORT = int(_env("MQTT_PORT", "1883"))
MQTT_USERNAME = _env("MQTT_USERNAME", "")
MQTT_KEY = _env("MQTT_KEY", "")
HAS_MQTT_CONFIG = bool(MQTT_BROKER)
if not HAS_MQTT_CONFIG:
    print("No MQTT_BROKER in settings.toml — MQTT disabled")


funhouse = FunHouse(default_bg=0x000000, scale=1)
sensors = Sensors(funhouse.peripherals, temp_offset_c=TEMP_OFFSET_C)
history = History(capacity=config.HISTORY_CAPACITY)
ui = UI(funhouse.display)


external_pir = None
if EXTERNAL_PIR_PIN:
    try:
        ext_pin = getattr(board, EXTERNAL_PIR_PIN)
        external_pir = digitalio.DigitalInOut(ext_pin)
        external_pir.direction = digitalio.Direction.INPUT
        print("External PIR on", EXTERNAL_PIR_PIN)
    except Exception as e:
        print("External PIR setup failed on {}: {}".format(EXTERNAL_PIR_PIN, e))
        external_pir = None


class Net:
    def __init__(self):
        self.mqtt_ok = False
        self._tried = False

    @property
    def wifi_ok(self):
        try:
            return bool(wifi.radio.connected)
        except Exception:
            return False

    def setup_mqtt(self):
        if not HAS_MQTT_CONFIG or self._tried:
            return
        self._tried = True
        try:
            funhouse.network.init_mqtt(
                MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_KEY
            )
            funhouse.network.mqtt_connect()
            self.mqtt_ok = True
            print("MQTT connected to", MQTT_BROKER)
        except Exception as e:
            print("MQTT setup failed:", e)
            self.mqtt_ok = False

    def publish(self, reading):
        if not self.mqtt_ok:
            return
        try:
            payload = {
                "temperature": reading.temp_c,
                "feels_like": reading.feels_c,
                "humidity": reading.humidity,
                "pressure": reading.pressure,
                "gas": reading.gas,
                "dewpoint": reading.dewpoint_c,
                "comfort": reading.comfort,
                "light": reading.light,
                "pm10_env": reading.pm10,
                "pm25_env": reading.pm25,
                "pm100_env": reading.pm100,
                "aqi": reading.aqi,
                "particles": reading.particles,
            }
            funhouse.peripherals.led = True
            funhouse.network.mqtt_publish(MQTT_TOPIC, json.dumps(payload))
            funhouse.peripherals.led = False
        except Exception as e:
            print("MQTT publish failed:", e)
            self.mqtt_ok = False
            self._tried = False


net = Net()
net.setup_mqtt()


# AQI -> (lit_count, color, brightness) — off when good, escalates with severity
def dotstar_state(aqi):
    if aqi is None or aqi <= 50:
        return 0, 0x000000, 0.0
    if aqi <= 100:
        return 1, 0xFFFF00, 0.06   # Moderate: yellow, dim
    if aqi <= 150:
        return 2, 0xFF7E00, 0.12   # Sensitive: orange
    if aqi <= 200:
        return 3, 0xFF2200, 0.22   # Unhealthy: red
    if aqi <= 300:
        return 4, 0xFF0000, 0.36   # Very unhealthy
    return 5, 0xCC0033, 0.55       # Hazardous


def paint_dotstars(reading, idle_sec):
    if idle_sec >= SLEEP_AFTER:
        funhouse.peripherals.dotstars.brightness = 0.0
        return

    n, color, bright = dotstar_state(reading.aqi)
    colors = [color if i < n else 0x000000 for i in range(5)]
    funhouse.peripherals.set_dotstars(*colors)
    if idle_sec >= DIM_AFTER:
        bright *= 0.4
    funhouse.peripherals.dotstars.brightness = bright


def compute_brightness(light, idle_sec):
    if idle_sec >= SLEEP_AFTER:
        return 0.0
    if idle_sec >= DIM_AFTER:
        return 0.15
    if light is None:
        return 0.6
    a = light / 5000.0
    if a < 0.3:
        a = 0.3
    if a > 1.0:
        a = 1.0
    return a


def step_toward(current, target, step):
    if abs(target - current) <= step:
        return target
    return current + step if target > current else current - step


class _SerialB64Stream:
    """File-like sink that base64-encodes whatever's written to it and prints
    one line at a time. Lets us capture a BMP without buffering it in RAM."""

    LINE_BYTES = 60  # 60 raw bytes -> 80 base64 chars per line

    def __init__(self):
        self._buf = bytearray()

    def write(self, data):
        import binascii

        if self._buf:
            data = bytes(self._buf) + bytes(data)
            self._buf = bytearray()
        n = self.LINE_BYTES
        i = 0
        end = len(data)
        while end - i >= n:
            print(binascii.b2a_base64(data[i:i + n]).rstrip(b"\n").decode())
            i += n
        if i < end:
            self._buf.extend(data[i:])
        return end

    def close(self):
        import binascii

        if self._buf:
            print(binascii.b2a_base64(bytes(self._buf)).rstrip(b"\n").decode())
            self._buf = bytearray()


def take_screenshot():
    print("\n===SCREENSHOT-START===")
    try:
        from adafruit_bitmapsaver import save_pixels

        sink = _SerialB64Stream()
        save_pixels(sink, funhouse.display)
        sink.close()
    except Exception as e:
        print("screenshot error:", e)
    print("===SCREENSHOT-END===")


def maybe_handle_serial():
    if not supervisor.runtime.serial_bytes_available:
        return
    try:
        ch = sys.stdin.read(1)
    except Exception:
        return
    if ch == "s":
        take_screenshot()


def handle_buttons(reading):
    """Returns True if a button was pressed."""
    if funhouse.peripherals.button_up:
        ui.prev_screen()
    elif funhouse.peripherals.button_down:
        ui.next_screen()
    elif funhouse.peripherals.button_sel:
        scr = ui.current_screen()
        if isinstance(scr, TrendScreen):
            scr.cycle_metric()
        else:
            ui.toggle_units()
    else:
        return False
    ui.update(
        reading, history, net.wifi_ok, net.mqtt_ok, history_interval=HISTORY_INTERVAL
    )
    return True


last_sensor = 0.0
last_history = 0.0
last_mqtt = 0.0
last_input = time.monotonic()
brightness = 0.6
manual_until = 0.0  # while now < this, the slider value drives brightness

# PIRs latch HIGH for several seconds per detection, so polling level was
# resetting last_input continuously. Track when each PIR went HIGH and
# only count it as activity once it has held HIGH for PIR_SUSTAIN_SEC —
# brief blips are ignored, which knocks the effective sensitivity down.
internal_pir_high_since = None
internal_pir_counted = False
external_pir_high_since = None
external_pir_counted = False

reading = sensors.read()
history.add(reading)
ui.update(reading, history, net.wifi_ok, net.mqtt_ok, history_interval=HISTORY_INTERVAL)

print("Weather station running.")

while True:
    now = time.monotonic()

    maybe_handle_serial()

    if handle_buttons(reading):
        last_input = now
        time.sleep(DEBOUNCE)

    internal_pir = bool(funhouse.peripherals.pir_sensor)
    if internal_pir:
        if internal_pir_high_since is None:
            internal_pir_high_since = now
        elif not internal_pir_counted and now - internal_pir_high_since >= PIR_SUSTAIN_SEC:
            last_input = now
            internal_pir_counted = True
    else:
        internal_pir_high_since = None
        internal_pir_counted = False

    if external_pir is not None:
        ext = bool(external_pir.value)
        if ext:
            if external_pir_high_since is None:
                external_pir_high_since = now
            elif not external_pir_counted and now - external_pir_high_since >= PIR_SUSTAIN_SEC:
                last_input = now
                external_pir_counted = True
        else:
            external_pir_high_since = None
            external_pir_counted = False

    slider = funhouse.peripherals.slider
    if slider is not None:
        last_input = now
        manual_until = now + 5.0
        target = max(0.05, slider)
    elif now < manual_until:
        target = brightness  # hold last manual setting briefly
    else:
        target = compute_brightness(reading.light, now - last_input)

    brightness = step_toward(brightness, target, 0.04)
    funhouse.display.brightness = brightness
    screen_on = brightness > 0.01

    if now - last_sensor >= SENSOR_INTERVAL:
        last_sensor = now
        reading = sensors.read()
        if now - last_history >= HISTORY_INTERVAL:
            history.add(reading)
            last_history = now
        # Only redraw while the screen is actually visible
        if screen_on:
            ui.update(
                reading, history, net.wifi_ok, net.mqtt_ok,
                history_interval=HISTORY_INTERVAL,
            )

    paint_dotstars(reading, now - last_input)

    if HAS_MQTT_CONFIG and now - last_mqtt >= MQTT_INTERVAL:
        last_mqtt = now
        if not net.mqtt_ok:
            net.setup_mqtt()
        net.publish(reading)

    time.sleep(LOOP_SLEEP)
