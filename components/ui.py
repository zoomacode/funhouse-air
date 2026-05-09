"""Display UI: status bar, three screens, hint bar, themed."""

import displayio
import terminalio
import bitmaptools
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.triangle import Triangle
from adafruit_bitmap_font import bitmap_font


W, H = 240, 240
BAR_H = 22
HINT_H = 22

BG = 0x0A0F1F
PANEL = 0x121A33
FG = 0xFFFFFF
DIM = 0x99A8C8
MUTED = 0x4A5878
ACCENT = 0x00DDFF
WARN = 0xFFC500
GOOD = 0x00E07A
BAD = 0xFF4555


def _arrow(direction, x, y, color):
    if direction == 1:
        return Triangle(x, y - 8, x - 7, y + 5, x + 7, y + 5, fill=color, outline=color)
    if direction == -1:
        return Triangle(x, y + 8, x - 7, y - 5, x + 7, y - 5, fill=color, outline=color)
    return Rect(x - 7, y - 2, 15, 4, fill=color)


def _trend_color(direction):
    if direction == 1:
        return WARN
    if direction == -1:
        return ACCENT
    return MUTED


def _is_light(rgb):
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140


def _temp_str(c, units):
    if c is None:
        return "—"
    if units == "F":
        return "{:.1f}".format(c * 9.0 / 5.0 + 32.0)
    return "{:.1f}".format(c)


class StatusBar:
    def __init__(self):
        self.group = displayio.Group()
        self.group.append(Rect(0, 0, W, BAR_H, fill=PANEL))
        self.group.append(Rect(0, BAR_H - 1, W, 1, fill=MUTED))

        self.title = label.Label(terminalio.FONT, text="--", color=ACCENT, scale=1)
        self.title.anchor_point = (0.0, 0.5)
        self.title.anchored_position = (8, BAR_H // 2)
        self.group.append(self.title)

        self.right = label.Label(terminalio.FONT, text="", color=DIM, scale=1)
        self.right.anchor_point = (1.0, 0.5)
        self.right.anchored_position = (W - 8, BAR_H // 2)
        self.group.append(self.right)

    def set_screen(self, index, total, name):
        self.title.text = "{}/{}  {}".format(index + 1, total, name.upper())

    def set_indicators(self, wifi_ok, mqtt_ok):
        wifi = "WiFi" if wifi_ok else "----"
        mqtt = "MQTT" if mqtt_ok else "----"
        self.right.text = "{}  {}".format(wifi, mqtt)


class HintBar:
    def __init__(self):
        self.group = displayio.Group()
        y0 = H - HINT_H
        self.group.append(Rect(0, y0, W, HINT_H, fill=PANEL))
        self.group.append(Rect(0, y0, W, 1, fill=MUTED))

        ymid = y0 + HINT_H // 2
        self.up = label.Label(terminalio.FONT, text="", color=DIM, scale=2)
        self.up.anchor_point = (0.0, 0.5)
        self.up.anchored_position = (6, ymid)
        self.group.append(self.up)

        self.sel = label.Label(terminalio.FONT, text="", color=DIM, scale=2)
        self.sel.anchor_point = (0.5, 0.5)
        self.sel.anchored_position = (W // 2, ymid)
        self.group.append(self.sel)

        self.dn = label.Label(terminalio.FONT, text="", color=DIM, scale=2)
        self.dn.anchor_point = (1.0, 0.5)
        self.dn.anchored_position = (W - 6, ymid)
        self.group.append(self.dn)

    def set(self, up, sel, dn):
        self.up.text = "^" + up
        self.sel.text = sel
        self.dn.text = dn + "v"


class Screen:
    name = "Screen"
    HINTS = ("Up", "Sel", "Dn")

    def __init__(self, big_font):
        self.big_font = big_font
        self.group = displayio.Group()

    def update(self, r, history, units):
        pass


class NowScreen(Screen):
    name = "Now"
    HINTS = ("Trend", "F/C", "Air")

    def __init__(self, big_font):
        super().__init__(big_font)
        body_top = BAR_H

        # BIG temp
        self.temp = label.Label(big_font, text="--.-", color=FG, scale=2)
        self.temp.anchor_point = (0.5, 0.5)
        self.temp.anchored_position = (W // 2 - 14, body_top + 32)
        self.group.append(self.temp)

        self.unit_lbl = label.Label(big_font, text="°C", color=ACCENT, scale=1)
        self.unit_lbl.anchor_point = (0.0, 0.0)
        self.unit_lbl.anchored_position = (W // 2 + 70, body_top + 14)
        self.group.append(self.unit_lbl)

        self._temp_trend_xy = (W - 22, body_top + 32)
        self._temp_trend = _arrow(0, *self._temp_trend_xy, MUTED)
        self.group.append(self._temp_trend)

        # feels
        self.feels = label.Label(big_font, text="feels —", color=DIM, scale=1)
        self.feels.anchor_point = (0.5, 0.5)
        self.feels.anchored_position = (W // 2, body_top + 76)
        self.group.append(self.feels)

        # Hum row
        y_h = body_top + 108
        self.hum_label = label.Label(terminalio.FONT, text="HUM", color=DIM, scale=2)
        self.hum_label.anchor_point = (0.0, 0.5)
        self.hum_label.anchored_position = (10, y_h)
        self.group.append(self.hum_label)
        self.hum_val = label.Label(big_font, text="--%", color=FG, scale=1)
        self.hum_val.anchor_point = (1.0, 0.5)
        self.hum_val.anchored_position = (W - 30, y_h)
        self.group.append(self.hum_val)
        self._hum_trend_xy = (W - 14, y_h)
        self._hum_trend = _arrow(0, *self._hum_trend_xy, MUTED)
        self.group.append(self._hum_trend)

        # Pres row
        y_p = body_top + 142
        self.pres_label = label.Label(terminalio.FONT, text="PRES", color=DIM, scale=2)
        self.pres_label.anchor_point = (0.0, 0.5)
        self.pres_label.anchored_position = (10, y_p)
        self.group.append(self.pres_label)
        self.pres_val = label.Label(big_font, text="-- hPa", color=FG, scale=1)
        self.pres_val.anchor_point = (1.0, 0.5)
        self.pres_val.anchored_position = (W - 30, y_p)
        self.group.append(self.pres_val)
        self._pres_trend_xy = (W - 14, y_p)
        self._pres_trend = _arrow(0, *self._pres_trend_xy, MUTED)
        self.group.append(self._pres_trend)

        # AQI band
        self._aqi_y = body_top + 166
        self._aqi_band = Rect(0, self._aqi_y, W, 30, fill=MUTED)
        self.group.append(self._aqi_band)
        self.aqi_num = label.Label(big_font, text="AQI —", color=0x000000, scale=1)
        self.aqi_num.anchor_point = (0.0, 0.5)
        self.aqi_num.anchored_position = (10, self._aqi_y + 15)
        self.group.append(self.aqi_num)
        self.aqi_cat_text = label.Label(big_font, text="", color=0x000000, scale=1)
        self.aqi_cat_text.anchor_point = (1.0, 0.5)
        self.aqi_cat_text.anchored_position = (W - 10, self._aqi_y + 15)
        self.group.append(self.aqi_cat_text)

    def _swap_arrow(self, slot, xy, direction):
        try:
            self.group.remove(slot)
        except ValueError:
            pass
        new = _arrow(direction, *xy, _trend_color(direction))
        self.group.append(new)
        return new

    def update(self, r, history, units):
        self.temp.text = _temp_str(r.temp_c, units)
        self.unit_lbl.text = "°" + units

        if r.feels_c is not None:
            f = r.feels_c if units == "C" else r.feels_c * 9.0 / 5.0 + 32.0
            self.feels.text = "feels {:.1f}°{}".format(f, units)
        else:
            self.feels.text = "feels —"

        self.hum_val.text = "{:.0f}%".format(r.humidity) if r.humidity is not None else "--%"
        self.pres_val.text = (
            "{:.0f}hPa".format(r.pressure) if r.pressure is not None else "-- hPa"
        )

        self._temp_trend = self._swap_arrow(
            self._temp_trend, self._temp_trend_xy, history.trend("temp_c")
        )
        self._hum_trend = self._swap_arrow(
            self._hum_trend, self._hum_trend_xy, history.trend("humidity")
        )
        self._pres_trend = self._swap_arrow(
            self._pres_trend, self._pres_trend_xy, history.trend("pressure")
        )

        self._aqi_band.fill = r.aqi_color if r.aqi is not None else MUTED
        if r.aqi is not None:
            text_color = 0x000000 if _is_light(r.aqi_color) else 0xFFFFFF
            self.aqi_num.text = "AQI {}".format(r.aqi)
            self.aqi_cat_text.text = r.aqi_label.upper()
            self.aqi_num.color = text_color
            self.aqi_cat_text.color = text_color
        else:
            self.aqi_num.text = "AQI —"
            self.aqi_cat_text.text = ""
            self.aqi_num.color = 0xFFFFFF


class AirScreen(Screen):
    name = "Air"
    HINTS = ("Now", "F/C", "Trend")

    def __init__(self, big_font):
        super().__init__(big_font)
        body_top = BAR_H

        title = label.Label(terminalio.FONT, text="AIR QUALITY", color=ACCENT, scale=2)
        title.anchor_point = (0.5, 0.0)
        title.anchored_position = (W // 2, body_top + 4)
        self.group.append(title)

        self.aqi_big = label.Label(big_font, text="—", color=FG, scale=2)
        self.aqi_big.anchor_point = (0.5, 0.5)
        self.aqi_big.anchored_position = (W // 2, body_top + 60)
        self.group.append(self.aqi_big)

        self.aqi_cat = label.Label(big_font, text="—", color=DIM, scale=1)
        self.aqi_cat.anchor_point = (0.5, 0.5)
        self.aqi_cat.anchored_position = (W // 2, body_top + 102)
        self.group.append(self.aqi_cat)

        # PM concentrations row (env)
        y_pm = body_top + 132
        self.pm10 = self._kv("PM1", "—", 40, y_pm)
        self.pm25 = self._kv("PM2.5", "—", W // 2, y_pm)
        self.pm100 = self._kv("PM10", "—", W - 40, y_pm)

        # Particle counts row 1
        y_p1 = body_top + 168
        self.p03 = self._kv(">.3um", "—", 40, y_p1)
        self.p05 = self._kv(">.5um", "—", W // 2, y_p1)
        self.p10 = self._kv(">1um", "—", W - 40, y_p1)

        # Particle counts row 2
        y_p2 = body_top + 192
        self.p25 = self._kv(">2.5um", "—", 40, y_p2)
        self.p50 = self._kv(">5um", "—", W // 2, y_p2)
        self.p100 = self._kv(">10um", "—", W - 40, y_p2)

    def _kv(self, key, val, x, y):
        k = label.Label(terminalio.FONT, text=key, color=MUTED, scale=1)
        k.anchor_point = (0.5, 0.0)
        k.anchored_position = (x, y - 1)
        self.group.append(k)
        v = label.Label(self.big_font, text=val, color=FG, scale=1)
        v.anchor_point = (0.5, 0.0)
        v.anchored_position = (x, y + 11)
        self.group.append(v)
        return v

    def update(self, r, history, units):
        if r.aqi is not None:
            self.aqi_big.text = str(r.aqi)
            self.aqi_big.color = r.aqi_color
            self.aqi_cat.text = r.aqi_label.upper()
            self.aqi_cat.color = r.aqi_color
        else:
            self.aqi_big.text = "—"
            self.aqi_big.color = DIM
            self.aqi_cat.text = "—"
            self.aqi_cat.color = DIM

        self.pm10.text = str(r.pm10) if r.pm10 is not None else "—"
        self.pm25.text = str(r.pm25) if r.pm25 is not None else "—"
        self.pm100.text = str(r.pm100) if r.pm100 is not None else "—"

        if r.particles:
            self.p03.text = str(r.particles["p03um"])
            self.p05.text = str(r.particles["p05um"])
            self.p10.text = str(r.particles["p10um"])
            self.p25.text = str(r.particles["p25um"])
            self.p50.text = str(r.particles["p50um"])
            self.p100.text = str(r.particles["p100um"])


class TrendScreen(Screen):
    name = "Trend"
    HINTS = ("Air", "Swap", "Now")

    METRICS = (
        ("temp_c", "TEMP", "{:.1f}", "C"),
        ("humidity", "HUMIDITY", "{:.0f}", "%"),
        ("pressure", "PRESSURE", "{:.0f}", ""),
        ("aqi", "AQI", "{:.0f}", ""),
    )

    def __init__(self, big_font):
        super().__init__(big_font)
        body_top = BAR_H

        self.title = label.Label(big_font, text="TEMP", color=ACCENT, scale=1)
        self.title.anchor_point = (0.5, 0.0)
        self.title.anchored_position = (W // 2, body_top + 4)
        self.group.append(self.title)

        # Sparkline canvas
        self._spark_x = 36
        self._spark_y = body_top + 36
        self._spark_w = W - self._spark_x - 6
        self._spark_h = 110
        self._bitmap = displayio.Bitmap(self._spark_w, self._spark_h, 4)
        palette = displayio.Palette(4)
        palette[0] = BG
        palette[1] = ACCENT
        palette[2] = MUTED
        palette[3] = WARN
        self._bitmap.fill(0)
        self.group.append(
            displayio.TileGrid(
                self._bitmap, pixel_shader=palette, x=self._spark_x, y=self._spark_y
            )
        )

        # Y-axis labels (left of sparkline)
        self.hi_lbl = label.Label(terminalio.FONT, text="—", color=DIM, scale=1)
        self.hi_lbl.anchor_point = (1.0, 0.0)
        self.hi_lbl.anchored_position = (self._spark_x - 3, self._spark_y)
        self.group.append(self.hi_lbl)

        self.lo_lbl = label.Label(terminalio.FONT, text="—", color=DIM, scale=1)
        self.lo_lbl.anchor_point = (1.0, 1.0)
        self.lo_lbl.anchored_position = (self._spark_x - 3, self._spark_y + self._spark_h)
        self.group.append(self.lo_lbl)

        # X-axis time span (under sparkline, left)
        self.span_lbl = label.Label(terminalio.FONT, text="—", color=MUTED, scale=1)
        self.span_lbl.anchor_point = (0.0, 0.0)
        self.span_lbl.anchored_position = (self._spark_x, self._spark_y + self._spark_h + 2)
        self.group.append(self.span_lbl)

        # NOW marker (right of sparkline, bottom)
        self.now_x_lbl = label.Label(terminalio.FONT, text="now", color=MUTED, scale=1)
        self.now_x_lbl.anchor_point = (1.0, 0.0)
        self.now_x_lbl.anchored_position = (W - 6, self._spark_y + self._spark_h + 2)
        self.group.append(self.now_x_lbl)

        # Big NOW value below
        self.now_val = label.Label(big_font, text="—", color=FG, scale=2)
        self.now_val.anchor_point = (0.5, 0.5)
        self.now_val.anchored_position = (W // 2, self._spark_y + self._spark_h + 36)
        self.group.append(self.now_val)

        self._metric_idx = 0
        self._last_history_len = -1

    def cycle_metric(self):
        self._metric_idx = (self._metric_idx + 1) % len(self.METRICS)
        self._last_history_len = -1  # force redraw

    def update(self, r, history, units, history_interval=30.0):
        attr, title, fmt, suffix = self.METRICS[self._metric_idx]
        if attr == "temp_c" and units == "F":
            title = "TEMP °F"
            display_attr_vals = [v * 9.0 / 5.0 + 32.0 for v in history.values("temp_c")]
            self.title.text = "TEMP °F"
        else:
            display_attr_vals = history.values(attr)
            self.title.text = "{} {}".format(title, suffix).strip() or title

        if display_attr_vals:
            lo = min(display_attr_vals)
            hi = max(display_attr_vals)
            now = display_attr_vals[-1]
            self.hi_lbl.text = fmt.format(hi)
            self.lo_lbl.text = fmt.format(lo)
            self.now_val.text = (fmt.format(now) + suffix).strip()
        else:
            self.hi_lbl.text = "—"
            self.lo_lbl.text = "—"
            self.now_val.text = "—"

        n = len(display_attr_vals)
        secs = int(n * history_interval)
        if secs >= 60:
            self.span_lbl.text = "-{}m".format(secs // 60)
        else:
            self.span_lbl.text = "-{}s".format(secs)

        # Only redraw sparkline if history changed
        if n != self._last_history_len:
            self._last_history_len = n
            self._draw_sparkline(display_attr_vals)

    def _draw_sparkline(self, vals):
        bm = self._bitmap
        w = self._spark_w
        h = self._spark_h
        bm.fill(0)
        # bottom border
        for x in range(w):
            bm[x, h - 1] = 2

        if len(vals) < 2:
            return

        lo = min(vals)
        hi = max(vals)
        rng = hi - lo
        if rng < 1e-6:
            rng = 1.0

        n = len(vals)
        last_x = -1
        last_y = -1
        for i, v in enumerate(vals):
            x = int(i * (w - 1) / max(1, n - 1))
            y = int((h - 2) - (v - lo) / rng * (h - 4))
            if 0 <= x < w and 0 <= y < h:
                if last_x >= 0:
                    bitmaptools.draw_line(bm, last_x, last_y, x, y, 1)
                last_x = x
                last_y = y


class UI:
    def __init__(self, display):
        self.display = display
        self.units = "C"

        try:
            self.big_font = bitmap_font.load_font("/fonts/Arial-Bold-24.pcf")
        except Exception as e:
            print("Falling back to terminalio.FONT for big_font:", e)
            self.big_font = terminalio.FONT

        self.root = displayio.Group()
        self._bg = Rect(0, 0, W, H, fill=BG)
        self.root.append(self._bg)

        self.status = StatusBar()
        self.root.append(self.status.group)

        self._content = displayio.Group()
        self.root.append(self._content)

        self.hint = HintBar()
        self.root.append(self.hint.group)

        self.screens = (
            NowScreen(self.big_font),
            AirScreen(self.big_font),
            TrendScreen(self.big_font),
        )
        self._current = 0
        self._content.append(self.screens[0].group)
        self._apply_screen_chrome()

        display.root_group = self.root
        display.auto_refresh = False

    def _apply_screen_chrome(self):
        scr = self.screens[self._current]
        self.status.set_screen(self._current, len(self.screens), scr.name)
        self.hint.set(*scr.HINTS)

    def next_screen(self):
        self._switch_to((self._current + 1) % len(self.screens))

    def prev_screen(self):
        self._switch_to((self._current - 1) % len(self.screens))

    def _switch_to(self, idx):
        while len(self._content):
            self._content.pop()
        self._current = idx
        self._content.append(self.screens[idx].group)
        self._apply_screen_chrome()

    def current_screen(self):
        return self.screens[self._current]

    def toggle_units(self):
        self.units = "F" if self.units == "C" else "C"

    def update(self, reading, history, wifi_ok, mqtt_ok, history_interval=30.0):
        self.status.set_indicators(wifi_ok, mqtt_ok)
        scr = self.current_screen()
        if isinstance(scr, TrendScreen):
            scr.update(reading, history, self.units, history_interval=history_interval)
        else:
            scr.update(reading, history, self.units)
        self.display.refresh()
