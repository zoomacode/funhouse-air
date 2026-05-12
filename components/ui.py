"""Display UI: status bar, three screens, left-side hint column, themed.

Tunable knobs (font scales, colors, comfort thresholds, layout toggles)
live in components/config.py — edit there, not here.
"""

import displayio
import terminalio
import bitmaptools
from adafruit_display_text import label
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.triangle import Triangle
from adafruit_bitmap_font import bitmap_font

from components import config


W, H = 240, 240
BAR_H = 22
LEFT_PAD = 32  # vertical hint strip on the left, aligned with physical buttons

CONTENT_X = LEFT_PAD
CONTENT_W = W - LEFT_PAD
CONTENT_CX = LEFT_PAD + CONTENT_W // 2

BG = config.COLOR_BG
PANEL = config.COLOR_PANEL
FG = config.COLOR_FG
DIM = config.COLOR_DIM
MUTED = config.COLOR_MUTED
ACCENT = config.COLOR_ACCENT
WARN = config.COLOR_WARN
GOOD = config.COLOR_GOOD
BAD = config.COLOR_BAD


def _arrow(direction, x, y, color):
    if direction == 1:
        return Triangle(x, y - 8, x - 7, y + 5, x + 7, y + 5, fill=color, outline=color)
    if direction == -1:
        return Triangle(x, y + 8, x - 7, y - 5, x + 7, y - 5, fill=color, outline=color)
    # Flat / OK: small filled circle (greenish when good)
    return Circle(x, y, 5, fill=color, outline=color)


def _trend_color(direction):
    if direction == 1:
        return WARN
    if direction == -1:
        return ACCENT
    return MUTED


def _comfort_indicator(value, lo, hi, soft_lo, soft_hi):
    """Compare value to a healthy range.

    Returns (direction, color):
      -1 = below range, 0 = inside, +1 = above range.
      Color: GOOD inside soft band, WARN in fringe, BAD beyond hard threshold.
    """
    if value is None:
        return 0, MUTED
    if value < lo:
        return -1, BAD
    if value < soft_lo:
        return -1, WARN
    if value <= soft_hi:
        return 0, GOOD
    if value <= hi:
        return 1, WARN
    return 1, BAD


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
        self.group.append(Rect(LEFT_PAD, 0, CONTENT_W, BAR_H, fill=PANEL))
        self.group.append(Rect(LEFT_PAD, BAR_H - 1, CONTENT_W, 1, fill=MUTED))

        self.title = label.Label(terminalio.FONT, text="--", color=ACCENT, scale=1)
        self.title.anchor_point = (0.0, 0.5)
        self.title.anchored_position = (LEFT_PAD + 6, BAR_H // 2)
        self.group.append(self.title)

        # Right-aligned: MQTT, WiFi (rightmost two pills)
        self.wifi_lbl = label.Label(terminalio.FONT, text="WIFI", color=MUTED, scale=1)
        self.wifi_lbl.anchor_point = (1.0, 0.5)
        self.wifi_lbl.anchored_position = (W - 6, BAR_H // 2)
        self.group.append(self.wifi_lbl)

        self.mqtt_lbl = label.Label(terminalio.FONT, text="MQTT", color=MUTED, scale=1)
        self.mqtt_lbl.anchor_point = (1.0, 0.5)
        self.mqtt_lbl.anchored_position = (W - 38, BAR_H // 2)
        self.group.append(self.mqtt_lbl)

    def set_screen(self, index, total, name):
        self.title.text = "{}/{}  {}".format(index + 1, total, name.upper())

    def set_indicators(self, wifi_ok, mqtt_ok):
        self.wifi_lbl.color = GOOD if wifi_ok else MUTED
        self.mqtt_lbl.color = GOOD if mqtt_ok else MUTED


class LeftHints:
    """Vertical column of three hint blocks aligned with physical buttons."""

    def __init__(self):
        self.group = displayio.Group()
        # Strip background spans below status bar so it doesn't cover it
        self.group.append(Rect(0, BAR_H, LEFT_PAD, H - BAR_H, fill=PANEL))
        self.group.append(Rect(LEFT_PAD - 1, BAR_H, 1, H - BAR_H, fill=MUTED))

        slot_h = (H - BAR_H) // 3  # ~72
        self._slot_h = slot_h
        cx = LEFT_PAD // 2

        # Static button symbols (triangles + "S")
        up_cy = BAR_H + slot_h // 3
        self.group.append(
            Triangle(cx, up_cy - 8, cx - 8, up_cy + 7, cx + 8, up_cy + 7,
                     fill=ACCENT, outline=ACCENT)
        )

        sel_cy = BAR_H + slot_h + slot_h // 3
        sel_lbl = label.Label(terminalio.FONT, text="S", color=ACCENT, scale=2)
        sel_lbl.anchor_point = (0.5, 0.5)
        sel_lbl.anchored_position = (cx, sel_cy)
        self.group.append(sel_lbl)

        dn_cy = BAR_H + 2 * slot_h + slot_h // 3
        self.group.append(
            Triangle(cx, dn_cy + 8, cx - 8, dn_cy - 7, cx + 8, dn_cy - 7,
                     fill=ACCENT, outline=ACCENT)
        )

        # Captioned labels under each symbol
        def _caption(slot_idx, top_offset):
            ly = BAR_H + slot_idx * slot_h + slot_h // 3 + top_offset
            l = label.Label(terminalio.FONT, text="", color=DIM, scale=1)
            l.anchor_point = (0.5, 0.5)
            l.anchored_position = (cx, ly)
            self.group.append(l)
            return l

        self.up_lbl = _caption(0, 22)
        self.sel_lbl = _caption(1, 22)
        self.dn_lbl = _caption(2, 22)

    def set(self, up, sel, dn):
        self.up_lbl.text = up
        self.sel_lbl.text = sel
        self.dn_lbl.text = dn


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

        # Layout differs based on whether the "feels" line is shown.
        # When feels is on, rows are tighter; when off, HUM/PRES get more
        # breathing room (recommended for SCALE_HUM=2).
        if config.SHOW_FEELS:
            y_temp = body_top + 30
            y_feels = body_top + 70
            y_h = body_top + 110
            y_p = body_top + 144
            y_aqi = body_top + 178
        else:
            y_temp = body_top + 28
            y_h = body_top + 90
            y_p = body_top + 152
            y_aqi = body_top + 182

        # BIG temp — single label including the unit
        self.temp = label.Label(big_font, text="--.-°C", color=FG, scale=config.SCALE_TEMP)
        self.temp.anchor_point = (0.5, 0.5)
        self.temp.anchored_position = (CONTENT_CX, y_temp)
        self.group.append(self.temp)

        if config.SHOW_FEELS:
            self.feels = label.Label(big_font, text="feels —", color=DIM, scale=config.SCALE_FEELS)
            self.feels.anchor_point = (0.5, 0.5)
            self.feels.anchored_position = (CONTENT_CX, y_feels)
            self.group.append(self.feels)
        else:
            self.feels = None

        # Hum row: small label, big value, comfort indicator
        self.hum_label = label.Label(terminalio.FONT, text="HUM", color=DIM, scale=1)
        self.hum_label.anchor_point = (0.0, 0.5)
        self.hum_label.anchored_position = (CONTENT_X + 6, y_h)
        self.group.append(self.hum_label)
        self.hum_val = label.Label(big_font, text="--%", color=FG, scale=config.SCALE_HUM)
        self.hum_val.anchor_point = (1.0, 0.5)
        self.hum_val.anchored_position = (W - 24, y_h)
        self.group.append(self.hum_val)
        self._hum_trend_xy = (W - 10, y_h)
        self._hum_trend = _arrow(0, *self._hum_trend_xy, MUTED)
        self.group.append(self._hum_trend)

        # Pres row — no hPa suffix; saves room
        self.pres_label = label.Label(terminalio.FONT, text="PRES", color=DIM, scale=1)
        self.pres_label.anchor_point = (0.0, 0.5)
        self.pres_label.anchored_position = (CONTENT_X + 6, y_p)
        self.group.append(self.pres_label)
        self.pres_val = label.Label(big_font, text="--", color=FG, scale=config.SCALE_PRES)
        self.pres_val.anchor_point = (1.0, 0.5)
        self.pres_val.anchored_position = (W - 24, y_p)
        self.group.append(self.pres_val)
        self._pres_trend_xy = (W - 10, y_p)
        self._pres_trend = _arrow(0, *self._pres_trend_xy, MUTED)
        self.group.append(self._pres_trend)

        # AQI band
        self._aqi_y = y_aqi
        aqi_h = H - y_aqi - 4  # extends to bottom (with 4 px margin)
        self._aqi_band = Rect(CONTENT_X, self._aqi_y, CONTENT_W, aqi_h, fill=MUTED)
        self.group.append(self._aqi_band)
        self.aqi_num = label.Label(
            big_font, text="AQI —", color=0x000000, scale=config.SCALE_AQI_BAND
        )
        self.aqi_num.anchor_point = (0.5, 0.5)
        self.aqi_num.anchored_position = (CONTENT_CX, self._aqi_y + aqi_h // 2)
        self.group.append(self.aqi_num)

    def _swap_arrow(self, slot, xy, direction, color=None):
        try:
            self.group.remove(slot)
        except ValueError:
            pass
        if color is None:
            color = _trend_color(direction)
        new = _arrow(direction, *xy, color)
        self.group.append(new)
        return new

    def update(self, r, history, units):
        self.temp.text = "{}°{}".format(_temp_str(r.temp_c, units), units)

        if self.feels is not None:
            if r.feels_c is not None:
                f = r.feels_c if units == "C" else r.feels_c * 9.0 / 5.0 + 32.0
                self.feels.text = "feels {:.1f}°{}".format(f, units)
            else:
                self.feels.text = "feels —"

        self.hum_val.text = "{:.0f}%".format(r.humidity) if r.humidity is not None else "--%"
        self.pres_val.text = (
            "{:.0f}".format(r.pressure) if r.pressure is not None else "--"
        )

        # Humidity comfort indicator (thresholds from config)
        h_lo_h, h_lo_s, h_hi_s, h_hi_h = config.HUMIDITY_THRESHOLDS
        hum_dir, hum_color = _comfort_indicator(
            r.humidity, h_lo_h, h_hi_h, h_lo_s, h_hi_s
        )
        self._hum_trend = self._swap_arrow(
            self._hum_trend, self._hum_trend_xy, hum_dir, color=hum_color
        )
        # Pressure comfort indicator (above/below normal range)
        p_lo_h, p_lo_s, p_hi_s, p_hi_h = config.PRESSURE_THRESHOLDS
        pres_dir, pres_color = _comfort_indicator(
            r.pressure, p_lo_h, p_hi_h, p_lo_s, p_hi_s
        )
        self._pres_trend = self._swap_arrow(
            self._pres_trend, self._pres_trend_xy, pres_dir, color=pres_color
        )

        self._aqi_band.fill = r.aqi_color if r.aqi is not None else MUTED
        if r.aqi is not None:
            self.aqi_num.text = "AQI {}".format(r.aqi)
            self.aqi_num.color = 0x000000 if _is_light(r.aqi_color) else 0xFFFFFF
        else:
            self.aqi_num.text = "AQI —"
            self.aqi_num.color = 0xFFFFFF


class AirScreen(Screen):
    name = "Air"
    HINTS = ("Now", "F/C", "Trend")

    def __init__(self, big_font):
        super().__init__(big_font)
        body_top = BAR_H

        title = label.Label(terminalio.FONT, text="AIR QUALITY", color=ACCENT, scale=2)
        title.anchor_point = (0.5, 0.0)
        title.anchored_position = (CONTENT_CX, body_top + 2)
        self.group.append(title)

        self.aqi_big = label.Label(big_font, text="—", color=FG, scale=config.SCALE_AQI_BIG)
        self.aqi_big.anchor_point = (0.5, 0.5)
        self.aqi_big.anchored_position = (CONTENT_CX, body_top + 50)
        self.group.append(self.aqi_big)

        self.aqi_cat = label.Label(big_font, text="—", color=DIM, scale=1)
        self.aqi_cat.anchor_point = (0.5, 0.5)
        self.aqi_cat.anchored_position = (CONTENT_CX, body_top + 90)
        self.group.append(self.aqi_cat)

        # PM concentrations / particle counts: 3 rows × 3 columns
        col_w = CONTENT_W // 3
        x_l = CONTENT_X + col_w // 2
        x_c = CONTENT_X + col_w + col_w // 2
        x_r = CONTENT_X + 2 * col_w + col_w // 2

        y_pm = body_top + 110
        self.pm10 = self._kv("PM1", "—", x_l, y_pm)
        self.pm25 = self._kv("PM2.5", "—", x_c, y_pm)
        self.pm100 = self._kv("PM10", "—", x_r, y_pm)

        y_p1 = body_top + 144
        self.p03 = self._kv(">.3", "—", x_l, y_p1)
        self.p05 = self._kv(">.5", "—", x_c, y_p1)
        self.p10 = self._kv(">1", "—", x_r, y_p1)

        y_p2 = body_top + 178
        self.p25 = self._kv(">2.5", "—", x_l, y_p2)
        self.p50 = self._kv(">5", "—", x_c, y_p2)
        self.p100 = self._kv(">10", "—", x_r, y_p2)

    def _kv(self, key, val, x, y):
        # Bigger label so it's actually readable, value just below
        k = label.Label(terminalio.FONT, text=key, color=MUTED, scale=2)
        k.anchor_point = (0.5, 0.0)
        k.anchored_position = (x, y)
        self.group.append(k)
        v = label.Label(self.big_font, text=val, color=FG, scale=1)
        v.anchor_point = (0.5, 0.0)
        v.anchored_position = (x, y + 16)
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
        ("humidity", "HUM", "{:.0f}", "%"),
        ("pressure", "PRES", "{:.0f}", ""),
        ("aqi", "AQI", "{:.0f}", ""),
    )

    def __init__(self, big_font):
        super().__init__(big_font)
        body_top = BAR_H

        self.title = label.Label(big_font, text="TEMP", color=ACCENT, scale=1)
        self.title.anchor_point = (0.5, 0.0)
        self.title.anchored_position = (CONTENT_CX, body_top + 4)
        self.group.append(self.title)

        # Sparkline (give a bit more room on left for axis labels at scale=2)
        self._spark_x = CONTENT_X + 50
        self._spark_y = body_top + 36
        self._spark_w = W - self._spark_x - 6
        self._spark_h = 130
        self._bitmap = displayio.Bitmap(self._spark_w, self._spark_h, 3)
        palette = displayio.Palette(3)
        palette[0] = BG
        palette[1] = ACCENT
        palette[2] = MUTED  # gridlines + bottom border
        self._bitmap.fill(0)
        self.group.append(
            displayio.TileGrid(
                self._bitmap, pixel_shader=palette, x=self._spark_x, y=self._spark_y
            )
        )

        ax_scale = config.SCALE_AXIS_LABELS
        # Y-axis labels (scale from config)
        self.hi_lbl = label.Label(terminalio.FONT, text="—", color=DIM, scale=ax_scale)
        self.hi_lbl.anchor_point = (1.0, 0.0)
        self.hi_lbl.anchored_position = (self._spark_x - 4, self._spark_y - 2)
        self.group.append(self.hi_lbl)

        self.lo_lbl = label.Label(terminalio.FONT, text="—", color=DIM, scale=ax_scale)
        self.lo_lbl.anchor_point = (1.0, 1.0)
        self.lo_lbl.anchored_position = (self._spark_x - 4, self._spark_y + self._spark_h)
        self.group.append(self.lo_lbl)

        # X-axis time span
        self.span_lbl = label.Label(terminalio.FONT, text="—", color=MUTED, scale=ax_scale)
        self.span_lbl.anchor_point = (0.0, 0.0)
        self.span_lbl.anchored_position = (self._spark_x, self._spark_y + self._spark_h + 4)
        self.group.append(self.span_lbl)

        self.now_x_lbl = label.Label(terminalio.FONT, text="now", color=MUTED, scale=ax_scale)
        self.now_x_lbl.anchor_point = (1.0, 0.0)
        self.now_x_lbl.anchored_position = (W - 6, self._spark_y + self._spark_h + 4)
        self.group.append(self.now_x_lbl)

        # NOW value below the chart
        self.now_val = label.Label(big_font, text="—", color=FG, scale=config.SCALE_NOW_VAL)
        self.now_val.anchor_point = (0.5, 0.5)
        self.now_val.anchored_position = (CONTENT_CX, self._spark_y + self._spark_h + 32)
        self.group.append(self.now_val)

        self._metric_idx = 0
        self._last_history_len = -1

    def cycle_metric(self):
        self._metric_idx = (self._metric_idx + 1) % len(self.METRICS)
        self._last_history_len = -1

    def update(self, r, history, units, history_interval=30.0):
        attr, title, fmt, suffix = self.METRICS[self._metric_idx]
        if attr == "temp_c" and units == "F":
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
        if secs >= 3600:
            self.span_lbl.text = "-{}h".format(secs // 3600)
        elif secs >= 60:
            self.span_lbl.text = "-{}m".format(secs // 60)
        else:
            self.span_lbl.text = "-{}s".format(secs)

        if n != self._last_history_len:
            self._last_history_len = n
            self._draw_sparkline(display_attr_vals)

    def _draw_sparkline(self, vals):
        bm = self._bitmap
        w = self._spark_w
        h = self._spark_h
        bm.fill(0)

        # Grid: solid bottom border, dotted horizontal lines at 1/3 and 2/3,
        # dotted vertical lines at quarters.
        h3 = h // 3
        h23 = 2 * h // 3
        for x in range(w):
            bm[x, h - 1] = 2
            if x % 3 == 0:
                bm[x, h3] = 2
                bm[x, h23] = 2
        wq = w // 4
        wh = w // 2
        wq3 = 3 * w // 4
        for y in range(h):
            if y % 3 == 0:
                bm[wq, y] = 2
                bm[wh, y] = 2
                bm[wq3, y] = 2

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

        self.hints = LeftHints()
        self.root.append(self.hints.group)

        self.status = StatusBar()
        self.root.append(self.status.group)

        self._content = displayio.Group()
        self.root.append(self._content)

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
        self.hints.set(*scr.HINTS)

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
