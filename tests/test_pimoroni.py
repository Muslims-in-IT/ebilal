"""Tests for pHAT BEAT support (pimoroni.py). No Pi, GPIO or /dev/input needed.

Run from the repo root:  .venv/bin/python -m pytest -q
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pimoroni as pm  # noqa: E402


class FakeLeds:
    flip = True

    def __init__(self):
        self.shows = 0
        self.lit = 0

    def set_pixel(self, *a, **k):
        self.lit += 1

    def set_all(self, *a, **k):
        pass

    def clear(self):
        self.lit = 0

    def show(self):
        self.shows += 1


class FakePlayer:
    def __init__(self, live=None, playing=""):
        self._live = live or []
        self.playing = playing
        self.status = "stopped"
        self.volume = 50
        self.calls = []

    def toggle(self):
        self.calls.append("toggle")
        if self.status == "playing":
            self.status = "stopped"
            return "stopped"
        self.playing = self.playing or (self._live[0] if self._live else None)
        if not self.playing:
            return None
        self.status = "playing"
        return self.playing

    def step(self, direction):
        self.calls.append(("step", direction))
        if not self._live:
            return None
        i = self._live.index(self.playing) if self.playing in self._live else (-1 if direction > 0 else 0)
        self.playing = self._live[(i + direction) % len(self._live)]
        return self.playing

    def nudge_volume(self, delta):
        self.volume = max(0, min(100, self.volume + delta))
        return self.volume


class NoReader:
    def __init__(self, callback):
        self.callback = callback

    def start(self):
        pass


def make(live=None, playing=""):
    player = FakePlayer(live=live, playing=playing)
    shutdowns = []
    c = pm.PhatBeatControls(player, leds=FakeLeds(), shutdown=lambda: shutdowns.append(1),
                            reader_factory=NoReader)
    c.REPEAT_DELAY, c.REPEAT_INTERVAL, c.SHUTDOWN_HOLD = 0.05, 0.02, 0.1
    c.start()
    return c, player, shutdowns


def press(c, code, hold=0.0):
    c.handle_key(code, pm.KEY_DOWN)
    if hold:
        time.sleep(hold)
    c.handle_key(code, pm.KEY_UP)


# ------------------------------------------------------------------ buttons
def test_play_pause_toggles():
    c, p, _ = make(live=["activestream"])
    press(c, pm.KEY_PLAYPAUSE)
    assert p.status == "playing"
    press(c, pm.KEY_PLAYPAUSE)
    assert p.status == "stopped"


def test_next_and_previous_wrap():
    c, p, _ = make(live=["a", "b", "c"], playing="a")
    press(c, pm.KEY_NEXTSONG)
    assert p.playing == "b"
    press(c, pm.KEY_PREVIOUSSONG)
    press(c, pm.KEY_PREVIOUSSONG)
    assert p.playing == "c"


def test_volume_tap_is_one_step():
    c, p, _ = make()
    press(c, pm.KEY_VOLUMEUP)
    time.sleep(0.1)
    assert p.volume == 55
    press(c, pm.KEY_VOLUMEDOWN)
    time.sleep(0.1)
    assert p.volume == 50


def test_volume_repeats_while_held_and_stops_on_release():
    c, p, _ = make()
    press(c, pm.KEY_VOLUMEUP, hold=0.2)  # delay 0.05 then every 0.02
    after_release = p.volume
    assert after_release >= 70
    time.sleep(0.15)
    assert p.volume == after_release  # stopped repeating


def test_tap_onoff_does_not_shut_down():
    c, _, shutdowns = make()
    press(c, pm.KEY_PROG1, hold=0.02)
    time.sleep(0.2)
    assert shutdowns == []


def test_hold_onoff_shuts_down_once():
    c, _, shutdowns = make()
    c.handle_key(pm.KEY_PROG1, pm.KEY_DOWN)
    time.sleep(0.3)
    c.handle_key(pm.KEY_PROG1, pm.KEY_UP)
    assert shutdowns == [1]


def test_kernel_autorepeat_events_are_ignored():
    c, p, _ = make()
    c.handle_key(pm.KEY_VOLUMEUP, pm.KEY_DOWN)
    c.handle_key(pm.KEY_VOLUMEUP, pm.KEY_REPEAT)
    c.handle_key(pm.KEY_VOLUMEUP, pm.KEY_UP)
    assert p.volume == 55


def test_nothing_live_is_safe():
    c, p, _ = make(live=[])
    press(c, pm.KEY_PLAYPAUSE)
    press(c, pm.KEY_NEXTSONG)
    assert p.status != "playing"


# ------------------------------------------------------------- event reader
def test_reader_decodes_kernel_events_from_a_pipe():
    got = []
    r, w = os.pipe()
    reader = pm.KeyReader(lambda code, value: got.append((code, value)), fds=[r])
    reader.start()
    ev = lambda t, code, value: struct.pack(pm.EVENT_FMT, 0, 0, t, code, value)
    os.write(w, ev(pm.EV_KEY, pm.KEY_PLAYPAUSE, 1) + ev(0, 0, 0)      # key + SYN
             + ev(pm.EV_KEY, 30, 1)                                   # not one of ours
             + ev(pm.EV_KEY, pm.KEY_PLAYPAUSE, 0))
    time.sleep(0.3)
    reader.stop()
    os.close(w)
    reader.join(2)
    assert got == [(pm.KEY_PLAYPAUSE, 1), (pm.KEY_PLAYPAUSE, 0)]


def test_find_key_devices_reads_capability_bitmap(tmp_path):
    bits = 8 * struct.calcsize("l")

    def cap(dev, codes):
        d = tmp_path / dev / "device" / "capabilities"
        d.mkdir(parents=True)
        words = [0] * 4
        for c in codes:
            words[c // bits] |= 1 << (c % bits)
        (d / "key").write_text(" ".join("%x" % w for w in reversed(words)) + "\n")

    cap("event2", [pm.KEY_PLAYPAUSE])   # a pHAT BEAT button
    cap("event3", [30, 31])             # a keyboard without media keys
    cap("event4", [pm.KEY_PROG1])       # the on/off button
    assert pm.find_key_devices(sys_root=str(tmp_path)) == ["/dev/input/event2", "/dev/input/event4"]


# --------------------------------------------------------------------- LEDs
class FakeGPIO:
    BCM, OUT = "BCM", "OUT"

    def __init__(self):
        self.bits = []
        self.dat = 0

    def setwarnings(self, *_): pass
    def setmode(self, *_): pass
    def setup(self, *_): pass

    def output(self, pins, values):
        pins = pins if isinstance(pins, list) else [pins]
        values = values if isinstance(values, (list, tuple)) else [values]
        for pin, value in zip(pins, values):
            if pin == pm.PhatBeatLeds.DAT:
                self.dat = 1 if value else 0
            elif pin == pm.PhatBeatLeds.CLK and value:
                self.bits.append(self.dat)


def frame_bytes(bits):
    return [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]


def test_led_frame_is_valid_apa102():
    g = FakeGPIO()
    leds = pm.PhatBeatLeds(gpio=g, flip=False)
    leds.set_pixel(0, 10, 20, 30, brightness=1.0, channel=0)
    leds.show()
    assert len(g.bits) == 32 + 16 * 32 + 32
    b = frame_bytes(g.bits)
    assert b[:4] == [0, 0, 0, 0]
    assert b[4:8] == [0xE0 | 31, 30, 20, 10]          # header, B, G, R
    assert b[-4:] == [0xFF] * 4


def test_led_columns_pimoroni_orientation():
    leds = pm.PhatBeatLeds(gpio=FakeGPIO(), flip=False)
    leds.set_pixel(0, 1, 1, 1, channel=0)
    leds.set_pixel(0, 2, 2, 2, channel=1)
    assert leds.pixels[0][:3] == [1, 1, 1]
    assert leds.pixels[15][:3] == [2, 2, 2]


def test_led_flip_moves_position_zero_to_other_end():
    leds = pm.PhatBeatLeds(gpio=FakeGPIO(), flip=True)
    leds.set_pixel(0, 1, 1, 1, channel=0)
    leds.set_pixel(0, 2, 2, 2, channel=1)
    assert leds.pixels[7][:3] == [1, 1, 1]
    assert leds.pixels[8][:3] == [2, 2, 2]


# ----------------------------------------------------------------- VU meter
def test_vu_level_scale():
    vu = pm.VuMeter(FakeLeds(), threading_lock())
    assert vu.level([0] * 100) == 0
    assert vu.level([32767, -32767] * 50) == 8                  # full scale
    quiet = int(32767 * 10 ** (-30 / 20))                        # -30 dBFS
    assert vu.level([quiet, -quiet] * 50) == 2


def threading_lock():
    import threading
    return threading.Lock()


def test_vu_reads_pipe_draws_and_clears_at_end():
    leds = RecordingLeds()
    vu = pm.VuMeter(leds, threading_lock())
    r, w = os.pipe()
    vu.attach(os.fdopen(r, "rb"))
    loud = struct.pack("<hh", 30000, -30000) * (pm.VuMeter.RATE // pm.VuMeter.FPS) * 3
    os.write(w, loud)
    os.close(w)                                                   # stream ends
    time.sleep(0.4)
    assert any(lit == (8, 8) for lit in leds.frames)
    assert leds.frames[-1] == (0, 0)


def test_vu_stays_quiet_while_busy():
    leds = RecordingLeds()
    vu = pm.VuMeter(leds, threading_lock(), busy=lambda: True)
    r, w = os.pipe()
    vu.attach(os.fdopen(r, "rb"))
    os.write(w, struct.pack("<hh", 30000, -30000) * 400)
    os.close(w)
    time.sleep(0.3)
    assert leds.frames == []


class RecordingLeds(FakeLeds):
    def __init__(self):
        super().__init__()
        self.frames = []
        self._cols = [0, 0]

    def set_pixel(self, x, *a, channel=None, **k):
        self._cols[channel] = max(self._cols[channel], x + 1)

    def clear(self):
        self._cols = [0, 0]

    def show(self):
        self.frames.append(tuple(self._cols))


# -------------------------------------------------------------- settings
def test_every_scheme_has_eight_colours():
    for name, colours in pm.SCHEMES.items():
        assert len(colours) == 8, name
        assert all(len(c) == 3 and all(0 <= v <= 255 for v in c) for c in colours), name


def test_apply_changes_settings_live():
    c, p, _ = make()
    c.vu = pm.VuMeter(c.leds, threading_lock())
    p.vu_sink = None
    assert c.apply(led_scheme="ocean", led_brightness=40, led_flip=False) is False
    assert c.vu.scheme == "ocean" and abs(c.vu.BRIGHTNESS - 0.4) < 1e-9
    assert c.settings()["led_flip"] is False
    c.vu_meter = False
    assert c.apply(vu_meter=False) is False           # no change, no restart
    assert c.apply(vu_meter=True) is True and p.vu_sink is not None
    assert c.apply(vu_meter=False) is True and p.vu_sink is None


def test_apply_rejects_unknown_scheme():
    c, _, _ = make()
    try:
        c.apply(led_scheme="disco")
        assert False, "should have raised"
    except ValueError:
        pass


def test_kitt_sweeps_then_clears():
    c, _, _ = make()
    leds = RecordingLeds()
    c.leds = leds
    c.kitt(sweeps=1, frame=0)
    assert len(leds.frames) >= 14          # up and back down
    assert leds.frames[-1] == (0, 0)
