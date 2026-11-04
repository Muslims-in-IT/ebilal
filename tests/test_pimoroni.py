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

    def output(self, pin, value):
        if pin == pm.PhatBeatLeds.DAT:
            self.dat = 1 if value else 0
        elif pin == pm.PhatBeatLeds.CLK and value:
            self.bits.append(self.dat)


def test_led_frame_is_valid_apa102():
    g = FakeGPIO()
    leds = pm.PhatBeatLeds(gpio=g)
    leds.set_pixel(0, 10, 20, 30, brightness=1.0, channel=0)
    leds.show()
    # start frame + 16 pixels x 32 bits + end frame
    assert len(g.bits) == 32 + 16 * 32 + 32
    assert g.bits[:32] == [0] * 32
    first = g.bits[32:64]
    byte = lambda b: int("".join(map(str, b)), 2)
    assert [byte(first[i:i + 8]) for i in range(0, 32, 8)] == [0xE0 | 31, 30, 20, 10]  # header, B, G, R
    assert g.bits[-32:] == [1] * 32


def test_led_right_column_is_reversed():
    leds = pm.PhatBeatLeds(gpio=FakeGPIO())
    leds.set_pixel(0, 1, 1, 1, channel=1)
    assert leds.pixels[15][:3] == [1, 1, 1]
