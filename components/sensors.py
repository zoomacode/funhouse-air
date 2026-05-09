"""Central sensor wrapper with derived metrics (AQI, heat index, comfort)."""

import time
import math
import board
import adafruit_bme680
from adafruit_pm25.i2c import PM25_I2C


# US EPA AQI breakpoints for PM2.5 (24-hr): (Cp_lo, Cp_hi, AQI_lo, AQI_hi, label, color)
_AQI_PM25 = (
    (0.0, 12.0, 0, 50, "Good", 0x00E400),
    (12.1, 35.4, 51, 100, "Moderate", 0xFFFF00),
    (35.5, 55.4, 101, 150, "Sensitive", 0xFF7E00),
    (55.5, 150.4, 151, 200, "Unhealthy", 0xFF0000),
    (150.5, 250.4, 201, 300, "Very Bad", 0x8F3F97),
    (250.5, 500.4, 301, 500, "Hazardous", 0x7E0023),
)


def aqi_from_pm25(pm25):
    """Linear interpolation across EPA PM2.5 breakpoints. Returns (aqi, label, color)."""
    c = float(pm25)
    for c_lo, c_hi, a_lo, a_hi, label, color in _AQI_PM25:
        if c <= c_hi:
            aqi = (a_hi - a_lo) / (c_hi - c_lo) * (c - c_lo) + a_lo
            return int(round(aqi)), label, color
    return 500, "Hazardous", 0x7E0023


def heat_index_f(temp_f, rh):
    """Rothfusz heat index. Below 80F, returns temp_f unchanged."""
    if temp_f < 80.0 or rh < 40.0:
        return temp_f
    t = temp_f
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    return hi


def dewpoint_c(temp_c, rh):
    """Magnus formula approximation."""
    if rh <= 0:
        return temp_c
    b, c = 17.625, 243.04
    gamma = math.log(rh / 100.0) + (b * temp_c) / (c + temp_c)
    return (c * gamma) / (b - gamma)


def comfort_score(temp_c, rh):
    """Subjective indoor comfort 0-100. Sweet spot ~21C / 45%RH."""
    # Temperature comfort: peak at 21C, falls off symmetrically
    t_score = max(0.0, 100.0 - abs(temp_c - 21.0) * 12.0)
    # Humidity comfort: peak in 40-50%, falls off
    if 40 <= rh <= 50:
        h_score = 100.0
    elif rh < 40:
        h_score = max(0.0, 100.0 - (40 - rh) * 4.0)
    else:
        h_score = max(0.0, 100.0 - (rh - 50) * 3.0)
    return int(round(0.6 * t_score + 0.4 * h_score))


class Reading:
    """A snapshot of all sensor values plus derived metrics."""

    __slots__ = (
        "ts",
        "temp_c",
        "humidity",
        "pressure",
        "gas",
        "feels_c",
        "dewpoint_c",
        "comfort",
        "pm10",
        "pm25",
        "pm100",
        "particles",
        "aqi",
        "aqi_label",
        "aqi_color",
        "light",
    )

    def __init__(self):
        self.ts = 0.0
        self.temp_c = None
        self.humidity = None
        self.pressure = None
        self.gas = None
        self.feels_c = None
        self.dewpoint_c = None
        self.comfort = None
        self.pm10 = None
        self.pm25 = None
        self.pm100 = None
        self.particles = None  # dict of size buckets, may be None
        self.aqi = None
        self.aqi_label = "—"
        self.aqi_color = 0x808080
        self.light = None

    @property
    def temp_f(self):
        if self.temp_c is None:
            return None
        return self.temp_c * 9.0 / 5.0 + 32.0

    @property
    def feels_f(self):
        if self.feels_c is None:
            return None
        return self.feels_c * 9.0 / 5.0 + 32.0


class Sensors:
    """Owns all hardware. Single read() pulls everything."""

    def __init__(self, peripherals, temp_offset_c=-2.0):
        self._peripherals = peripherals
        self._offset = temp_offset_c
        i2c = board.I2C()

        self._bme = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x76)
        self._bme.sea_level_pressure = 1013.25
        self._pm = PM25_I2C(i2c, None)

    def read(self):
        r = Reading()
        r.ts = time.monotonic()

        try:
            raw_t = self._bme.temperature + self._offset
            r.temp_c = raw_t
            r.humidity = self._bme.relative_humidity
            r.pressure = self._bme.pressure
            r.gas = self._bme.gas
            hi_f = heat_index_f(raw_t * 9.0 / 5.0 + 32.0, r.humidity)
            r.feels_c = (hi_f - 32.0) * 5.0 / 9.0
            r.dewpoint_c = dewpoint_c(raw_t, r.humidity)
            r.comfort = comfort_score(raw_t, r.humidity)
        except Exception as e:
            print("BME680 read failed:", e)

        try:
            data = self._pm.read()
            r.pm10 = data["pm10 env"]
            r.pm25 = data["pm25 env"]
            r.pm100 = data["pm100 env"]
            r.particles = {
                "p03um": data["particles 03um"],
                "p05um": data["particles 05um"],
                "p10um": data["particles 10um"],
                "p25um": data["particles 25um"],
                "p50um": data["particles 50um"],
                "p100um": data["particles 100um"],
            }
            aqi, label, color = aqi_from_pm25(r.pm25)
            r.aqi = aqi
            r.aqi_label = label
            r.aqi_color = color
        except Exception as e:
            print("PM25 read failed:", e)

        try:
            r.light = self._peripherals.light
        except Exception:
            pass

        return r
