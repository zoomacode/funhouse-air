import board
from digitalio import DigitalInOut, Direction, Pull

import adafruit_dps310
import adafruit_ahtx0
import adafruit_bme680
from adafruit_funhouse import FunHouse
from adafruit_display_shapes.circle import Circle
from components.air_quality import SensorReader as AirReader, BMEWrapper
import time
import json


is_secrets_imported = False
try:
    from secrets import secrets

    is_secrets_imported = True
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")

funhouse = FunHouse(
    default_bg=0x000000,
    scale=2,
)


def set_label_color(conditional, index, on_color):
    if conditional:
        funhouse.set_text_color(on_color, index)
    else:
        funhouse.set_text_color(0x606060, index)


def get_line_y(pos):
    return 5 + pos * 15


class WholeThing:
    def __init__(self) -> None:
        self._dotstart_brightness_def = 0.05
        self._backlight_brightnes_def = 0.50
        self._dotstart_brightness = self._dotstart_brightness_def
        self._backlight_brightnes = self._backlight_brightnes_def
        self._create_ui()
        self._init_sensors()

        topic_prefix = "funhouse"
        self._mqtt_topic = f"{topic_prefix}/state"
        self._light_state_topic = f"{topic_prefix}/light/state"
        self._light_command_topic = f"{topic_prefix}/light/set"

        if is_secrets_imported:
            self._mqtt_inited = False
            self._setup_mqtt()

        self._last_activity = time.monotonic()
        self._environment = self.build_environment()

    def _setup_mqtt(self):
        # Initialize a new MQTT Client object
        funhouse.network.init_mqtt(
            secrets["mqtt_broker"],
            secrets["mqtt_port"],
            secrets["aio_username"],
            secrets["aio_key"],
        )
        funhouse.network.on_mqtt_connect = (
            lambda client, userdata, result, payload: self._mqtt_connected(
                client, userdata, result, payload
            )
        )
        funhouse.network.on_mqtt_disconnect = lambda client: self._mqtt_disconnected(client)
        funhouse.network.on_mqtt_message = lambda client, topic, payload: self._mqtt_message(
            client, topic, payload
        )

        print("Attempting to connect to {}".format(secrets["mqtt_broker"]))
        try:
            funhouse.network.mqtt_connect()
            self._mqtt_inited = True
        except Exception as e:
            print(e)

    def _mqtt_connected(self, client, userdata, result, payload):
        self._status.fill = 0x00FF00
        self._status.outline = 0x008800
        funhouse.display.refresh()
        print("Connected to MQTT! Subscribing...")
        client.subscribe(self._light_command_topic)

    def _mqtt_disconnected(self, client):
        self._status.fill = 0xFF0000
        self._status.outline = 0x880000
        funhouse.display.refresh()

    def _mqtt_message(self, client, topic, payload):
        print("Topic {0} received new value: {1}".format(topic, payload))

    def _create_ui(self):
        funhouse.peripherals.set_dotstars(0x800000, 0x808000, 0x008000, 0x000080, 0x800080)
        funhouse.peripherals.dotstars.brightness = self._dotstart_brightness
        funhouse.display.brightness = self._backlight_brightnes

        # Create the labels

        # Don't display the splash yet to avoid
        # redrawing labels after each one is added
        funhouse.display.show(None)

        line_num = 0
        self._temp_label = funhouse.add_text(
            text="Temp:", text_position=(5, get_line_y(line_num)), text_color=0xFF00FF
        )
        line_num += 1
        self._pres_label = funhouse.add_text(
            text="Pres:", text_position=(5, get_line_y(line_num)), text_color=0xFF00FF
        )
        line_num += 1
        self._humid_label = funhouse.add_text(
            text="Humidity:", text_position=(5, get_line_y(line_num)), text_color=0xFF00FF
        )
        line_num += 1
        self._pmEnv_label = funhouse.add_text(
            text="PM1.0/2.5/10 units: ",
            text_position=(5, get_line_y(line_num)),
            text_color=0xFF00FF,
        )
        line_num += 1
        self._pmEnv_data_label = funhouse.add_text(
            text="", text_position=(30, get_line_y(line_num)), text_color=0xFFDDFF
        )
        line_num += 1
        self._pmPart_label = funhouse.add_text(
            text="PM.3/.5/1/2.5/5./10", text_position=(5, get_line_y(line_num)), text_color=0xFF00FF
        )
        line_num += 1
        self._pmPart_data_label = funhouse.add_text(
            text="", text_position=(15, get_line_y(line_num)), text_color=0xFFDDFF
        )
        line_num += 1
        funhouse.display.show(funhouse.splash)
        funhouse.display.auto_refresh = False

        # Adding an MQT connection status indicator
        self._status = Circle(110, 10, 7, fill=0xFF0000, outline=0x880000)
        funhouse.splash.append(self._status)

    def _init_sensors(self):

        i2c = board.I2C()
        self._dps310 = adafruit_dps310.DPS310(i2c)
        self._aht20 = adafruit_ahtx0.AHTx0(i2c)

        self._bme680 = BMEWrapper(i2c)
        self._air = AirReader(i2c)
        self._recent_air_data = self._air.read_data()

    def update_ui(self, print_data):
        # funhouse.display.show(None)
        funhouse.set_text("Temp: %0.1FC" % self._bme680.temperature, self._temp_label)
        funhouse.set_text("Pres: %dhPa" % self._bme680.pressure, self._pres_label)
        funhouse.set_text(f"Humid: {self._bme680.relative_humidity}%", self._humid_label)

        slider = funhouse.peripherals.slider
        if slider is not None:
            funhouse.peripherals.dotstars.brightness = slider

        air_data = self._air.read_data()
        if air_data is not None:
            evn_conc = air_data.env_concentration
            pm10um = evn_conc.pm10um
            pm25um = evn_conc.pm25um
            pm100um = evn_conc.pm100um
            funhouse.set_text(f"{pm10um}/{pm25um}/{pm100um}", self._pmEnv_data_label)

            parts = air_data.particles
            pm03um = parts.p03um
            pm05um = parts.p05um
            pm10um = parts.p10um
            pm25um = parts.p25um
            pm50um = parts.p50um
            pm100um = parts.p100um
            funhouse.set_text(
                f"{pm03um}/{pm05um}/{pm10um}/{pm25um}/{pm50um}/{pm100um}", self._pmPart_data_label
            )
        else:
            print("WARNING!!! Unable to read air quality data....")
        self._recent_air_data = air_data

        # funhouse.display.show(funhouse.splash)
        funhouse.display.refresh()

        if (
            funhouse.peripherals.button_sel
            or funhouse.peripherals.button_up
            or funhouse.peripherals.button_down
        ):
            self._last_activity = time.monotonic()
            self._dotstart_brightness = self._dotstart_brightness_def
            self._backlight_brightnes = self._backlight_brightnes_def
        elif (time.monotonic() - self._last_activity) > 5:
            self._dotstart_brightness = max(
                0.0, self._dotstart_brightness - 0.05 * self._dotstart_brightness_def
            )
            self._backlight_brightnes = max(
                0.0, self._backlight_brightnes - 0.05 * self._backlight_brightnes_def
            )
        sleepy = self._backlight_brightnes <= 0.0

        funhouse.peripherals.dotstars.brightness = self._dotstart_brightness
        funhouse.display.brightness = self._backlight_brightnes

        if print_data:
            print("aht20", self._aht20.temperature, None, self._aht20.relative_humidity)
            print("dps310", self._dps310.temperature, self._dps310.pressure, None)
            print(
                "bme680",
                self._bme680.temperature,
                self._bme680.pressure,
                self._bme680.relative_humidity,
                self._bme680.humidity,
                self._bme680.altitude,
                self._bme680.gas,
            )
            print(
                "perif",
                funhouse.peripherals.temperature,
                funhouse.peripherals.pressure,
                funhouse.peripherals.relative_humidity,
            )
            if air_data is not None:
                air_data.print()

        return sleepy

    def publish_to_mqtt(self):
        if is_secrets_imported and not self._mqtt_inited:
            self._setup_mqtt()

        if not self._mqtt_inited:
            return

        funhouse.peripherals.led = True
        print("Publishing to {}".format(self._mqtt_topic))
        data = json.dumps(self.environment)
        print(data)
        funhouse.network.mqtt_publish(self._mqtt_topic, data)
        funhouse.peripherals.led = False

    def build_environment(self):
        environment = {}
        environment["temperature"] = self._bme680.temperature - 5
        environment["pressure"] = self._bme680.pressure
        environment["humidity"] = self._bme680.relative_humidity
        environment["gas"] = self._bme680.relative_humidity
        environment["altitude"] = self._bme680.altitude
        environment["light"] = funhouse.peripherals.light

        air_data = self._recent_air_data
        if air_data is not None:
            environment["pm_units_env"] = air_data.env_concentration.__dict__
            environment["pm_units_std"] = air_data.std_concentration.__dict__
            environment["pm_particles"] = air_data.particles.__dict__

        return environment

    def update_environment(self):
        environment = self.build_environment()
        alpha = 0.97

        new_environment = decay_dicts(self._environment, environment, alpha)
        self._environment = new_environment

    @property
    def environment(self):
        return self._environment

    def alarm(self, on):
        if on:
            funhouse.peripherals.set_dotstars(0x800000, 0x800000, 0x800000, 0x800000, 0x800000)
            funhouse.peripherals.dotstars.brightness = 0.5
        else:
            funhouse.peripherals.set_dotstars(0x800000, 0x808000, 0x008000, 0x000080, 0x800080)


def decay_dicts(old_dict, new_dict, alpha=0.9):
    results = {}

    try:
        for k in new_dict:
            new_val = new_dict.get(k)
            old_val = old_dict.get(k)
            if new_val is None:
                results[k] = old_val
                print("New val for", k, "is None. Using the old one", old_val)
                continue
            if old_val is None:
                results[k] = new_val
                print("Old val for", k, "is None. Using the new one", new_val)
                continue
            results[k] = (
                decay_dicts(old_val, new_val, alpha)
                if isinstance(new_val, dict)
                else alpha * old_val + (1.0 - alpha) * new_val
            )
    except Exception as e:
        print(e)
        print("old", new_dict)
        print("new", old_dict)
        raise

    return results


thing = WholeThing()

DUMP_DATA_INTERVAL_SEC = 10
MQTT_PUBLISH_DATA_INTERVAL_SEC = 60
last_print_ts = time.monotonic()
last_mqtt_publish_ts = time.monotonic()

while True:
    print_data = False
    if (time.monotonic() - last_print_ts) > DUMP_DATA_INTERVAL_SEC:
        print_data = True
        last_print_ts = time.monotonic()

    sleepy = thing.update_ui(print_data)

    thing.update_environment()

    if (time.monotonic() - last_mqtt_publish_ts) > DUMP_DATA_INTERVAL_SEC:
        thing.publish_to_mqtt()
        last_mqtt_publish_ts = time.monotonic()

    try:
        sleep_sec = 2 if sleepy else 0.1
        funhouse.enter_light_sleep(sleep_sec)
        thing.alarm(False)
    except Exception as e:
        print("ALARM!!!!", e)
        thing.alarm(True)
