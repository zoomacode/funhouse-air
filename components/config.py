"""User-tunable settings for the FunHouse weather station.

Edit any value here and save — CircuitPython auto-reloads.
If something breaks, reset the device to recover.
"""

# ============================================================
# Sensor calibration
# ============================================================

# Subtract this from the raw BME680 temperature (deg C). External BME680
# in our setup reads ~2 C higher than an Aranet reference.
TEMP_OFFSET_C = -2.0


# ============================================================
# Timings (seconds)
# ============================================================

# How often to read sensors and refresh the screen
SENSOR_INTERVAL_SEC = 1.0

# How often to push a sample into the rolling history (used by sparkline
# and trend arrows). 30s × 240 samples = 2 hours of history.
HISTORY_INTERVAL_SEC = 30.0

# How often to publish to MQTT (when the broker is reachable)
MQTT_INTERVAL_SEC = 60.0

# Idle time before dimming the screen / putting it to sleep
DIM_AFTER_SEC = 30.0
SLEEP_AFTER_SEC = 180.0

# Sparkline history length (samples). Multiply by HISTORY_INTERVAL_SEC
# to get the time span shown on the Trend screen.
HISTORY_CAPACITY = 240  # 30 s * 240 = 7200 s = 2 h


# ============================================================
# External PIR
# ============================================================

# GPIO pin name where the PIR's OUT wire is connected. Set to None
# to disable the external PIR (the built-in one always works).
# DO NOT use D0 (boot strap pin) — the device won't boot.
EXTERNAL_PIR_PIN = "A0"


# ============================================================
# MQTT
# ============================================================

# Topic for the published JSON payload
MQTT_TOPIC = "funhouse/state"


# ============================================================
# Comfort thresholds (lo_hard, lo_soft, hi_soft, hi_hard)
# ============================================================
#   value <  lo_hard           -> red down arrow  (BAD low)
#   lo_hard <= value < lo_soft -> amber down      (warn low)
#   lo_soft <= value <= hi_soft-> green circle    (OK)
#   hi_soft < value <= hi_hard -> amber up        (warn high)
#   value > hi_hard            -> red up arrow    (BAD high)

HUMIDITY_THRESHOLDS = (30, 40, 50, 60)
PRESSURE_THRESHOLDS = (1005, 1010, 1020, 1025)


# ============================================================
# Font scales (1, 2, 3 ...)
# ============================================================
# Higher = bigger but blockier (PCF font scales by integer pixels).
# scale=1 with the bundled 24pt font is approximately desktop-clock height.

SCALE_TEMP = 2          # big temperature number on Now screen
SCALE_FEELS = 1         # "feels like" line under temp
SCALE_HUM = 2           # humidity value (e.g. "42%")
SCALE_PRES = 2          # pressure value (e.g. "1018")
SCALE_AQI_BAND = 1      # AQI text inside the colored band on Now
SCALE_AQI_BIG = 2       # AQI big number on Air screen
SCALE_NOW_VAL = 1       # NOW value at bottom of Trend screen
SCALE_AXIS_LABELS = 2   # min / max / time-span / "now" on Trend


# ============================================================
# Display behavior
# ============================================================

# Show the "feels like" line on the Now screen. Disable to give HUM and
# PRES rows more vertical breathing room (recommended when SCALE_HUM=2).
SHOW_FEELS = False


# ============================================================
# Theme (16-bit RGB integers)
# ============================================================

COLOR_BG = 0x0A0F1F
COLOR_PANEL = 0x121A33
COLOR_FG = 0xFFFFFF
COLOR_DIM = 0x99A8C8
COLOR_MUTED = 0x4A5878
COLOR_ACCENT = 0x00DDFF
COLOR_WARN = 0xFFC500
COLOR_GOOD = 0x00E07A
COLOR_BAD = 0xFF4555
