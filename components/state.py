"""Rolling history of readings for sparklines and trend arrows."""


class History:
    """Fixed-capacity ring buffer of Reading objects."""

    def __init__(self, capacity=120):
        self.capacity = capacity
        self._buf = []

    def add(self, reading):
        self._buf.append(reading)
        if len(self._buf) > self.capacity:
            self._buf.pop(0)

    def __len__(self):
        return len(self._buf)

    def latest(self):
        return self._buf[-1] if self._buf else None

    def values(self, attr):
        out = []
        for r in self._buf:
            v = getattr(r, attr, None)
            if v is not None:
                out.append(v)
        return out

    def trend(self, attr, window=10):
        """Compare mean of last `window` samples vs the previous `window`. Returns -1/0/+1."""
        vals = self.values(attr)
        if len(vals) < window * 2:
            return 0
        recent = vals[-window:]
        prior = vals[-window * 2 : -window]
        recent_avg = sum(recent) / len(recent)
        prior_avg = sum(prior) / len(prior)
        delta = recent_avg - prior_avg
        # Per-attribute thresholds so we don't flag noise
        thresholds = {
            "temp_c": 0.15,
            "humidity": 0.5,
            "pressure": 0.3,
            "pm25": 1.0,
            "aqi": 2.0,
        }
        threshold = thresholds.get(attr, 0.0)
        if delta > threshold:
            return 1
        if delta < -threshold:
            return -1
        return 0
