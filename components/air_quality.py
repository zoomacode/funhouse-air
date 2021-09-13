# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Example sketch to connect to PM2.5 sensor with either I2C or UART.
"""

# pylint: disable=unused-import
import time
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_pm25.i2c import PM25_I2C
import adafruit_bme680


class ConcentrationUnits:
    def __init__(self, pm10um, pm25um, pm100um) -> None:
        self.pm10um = pm10um
        self.pm25um = pm25um
        self.pm100um = pm100um

    def print(self) -> None:
        print("PM 1.0: %d\tPM2.5: %d\tPM10: %d" % (self.pm10um, self.pm25um, self.pm100um))


class Particles:
    def __init__(self, p03um, p05um, p10um, p25um, p50um, p100um) -> None:
        self.p03um = p03um
        self.p05um = p05um
        self.p10um = p10um
        self.p25um = p25um
        self.p50um = p50um
        self.p100um = p100um

    def print(self):
        print("Particles > 0.3um / 0.1L air:", self.p03um)
        print("Particles > 0.5um / 0.1L air:", self.p05um)
        print("Particles > 1.0um / 0.1L air:", self.p10um)
        print("Particles > 2.5um / 0.1L air:", self.p25um)
        print("Particles > 5.0um / 0.1L air:", self.p50um)
        print("Particles > 10 um / 0.1L air:", self.p100um)


class QualityData:
    def __init__(self, std_concentration, env_concentration, particles) -> None:
        self.std_concentration = std_concentration
        self.env_concentration = env_concentration
        self.particles = particles

    def print(self) -> None:
        print()
        print("Concentration Units (standard)")
        print("---------------------------------------")
        self.std_concentration.print()
        print("Concentration Units (environmental)")
        print("---------------------------------------")
        self.std_concentration.print()
        print("---------------------------------------")
        self.particles.print()
        print("---------------------------------------")


class SensorReader:
    def __init__(self, i2c) -> None:
        reset_pin = None
        # If you have a GPIO, its not a bad idea to connect it to the RESET pin
        # reset_pin = DigitalInOut(board.G0)
        # reset_pin.direction = Direction.OUTPUT
        # reset_pin.value = False

        # Create library object, use 'slow' 100KHz frequency!
        # i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
        # Connect to a PM2.5 sensor over I2C
        self.pm25 = PM25_I2C(i2c, reset_pin)

    def read_data(self):
        try:
            aqdata = self.pm25.read()
            std_concent = ConcentrationUnits(
                pm10um=aqdata["pm10 standard"],
                pm25um=aqdata["pm25 standard"],
                pm100um=aqdata["pm100 standard"],
            )
            env_concent = ConcentrationUnits(
                pm10um=aqdata["pm10 env"],
                pm25um=aqdata["pm25 env"],
                pm100um=aqdata["pm100 env"],
            )
            parts = Particles(
                p03um=aqdata["particles 03um"],
                p05um=aqdata["particles 05um"],
                p10um=aqdata["particles 10um"],
                p25um=aqdata["particles 25um"],
                p50um=aqdata["particles 50um"],
                p100um=aqdata["particles 100um"],
            )

            return QualityData(
                std_concentration=std_concent, env_concentration=env_concent, particles=parts
            )
        except RuntimeError:
            print("Unable to read from sensor, retrying...")
            return None


class BMEWrapper:
    def __init__(self, i2c) -> None:
        self._bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x76)
        self._bme680.sea_level_pressure = 1013.25
        # self._bme680.temperature_oversample = 8
        # self._bme680.humidity_oversample = 2
        # self._bme680.pressure_oversample = 4
        # self._bme680.filter_size = 3

        gas_reference = 0.0
        iters = 10
        for _ in range(iters):
            gas_reference += self._bme680.gas
        gas_reference /= iters
        self.gas_reference = gas_reference

    @property
    def temperature(self):
        return self._bme680.temperature

    @property
    def humidity(self):
        return self._bme680.humidity

    @property
    def relative_humidity(self):
        return self._bme680.relative_humidity

    @property
    def altitude(self):
        return self._bme680.altitude

    @property
    def gas(self):
        return self._bme680.gas

    @property
    def pressure(self):
        return self._bme680.pressure


def get_humidity_score(value, reference=40.0):
    if value < 38:
        return value / reference * 100

    if value <= 42:
        return 100

    return
