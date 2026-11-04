"""Tests for the pHAT BEAT physical controls and the pin-aware playlist.

Run from the repo root:  .venv/bin/python -m pytest -q
No Raspberry Pi or GPIO needed, the phatbeat module is faked.
"""
import os
import sys
import types
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakePhatBeat:
    """Minimal stand-in for the phatbeat library: records button handlers."""
    BTN_FASTFWD, BTN_REWIND, BTN_PLAYPAUSE = 5, 13, 6
    BTN_VOLUP, BTN_VOLDN, BTN_ONOFF = 16, 26, 12

    def __init__(self):
        self.handlers = {}
        self.hold_handlers = {}
        self.shown = 0

    def on(self, button, handler=None, repeat=True):
        self.handlers[button] = handler

    def hold(self, button, handler=None, repeat=True, hold_time=2):
        self.hold_handlers[button] = handler

    def clear(self, channel=None):
        pass

    def show(self):
        self.shown += 1

    def set_all(self, r, g, b, brightness=None, channel=None):
        pass

    def set_pixel(self, x, r, g, b, brightness=None, channel=None):
        pass


class FakePlayer:
    """Captures what the controls ask the player to do."""
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
        try:
            i = self._live.index(self.playing)
        except ValueError:
            i = -1 if direction > 0 else 0
        self.playing = self._live[(i + direction) % len(self._live)]
        return self.playing

    def nudge_volume(self, delta):
        self.calls.append(("vol", delta))
        self.volume = max(0, min(100, self.volume + delta))
        return self.volume


def make_controls(live=None, playing=""):
    from phatbeat_controls import PhatBeatControls
    pb = FakePhatBeat()
    player = FakePlayer(live=live, playing=playing)
    shutdowns = []
    c = PhatBeatControls(player, phatbeat=pb, shutdown=lambda: shutdowns.append(True))
    c.REPEAT_MIN_INTERVAL = 0  # don't debounce in tests
    c.start()
    return c, pb, player, shutdowns


def test_buttons_are_registered():
    c, pb, _, _ = make_controls()
    for b in (pb.BTN_PLAYPAUSE, pb.BTN_FASTFWD, pb.BTN_REWIND, pb.BTN_VOLUP, pb.BTN_VOLDN):
        assert pb.handlers.get(b) is not None
    # Shutdown is on HOLD, not a tap
    assert pb.hold_handlers.get(pb.BTN_ONOFF) is not None


def test_play_pause_toggles():
    c, pb, player, _ = make_controls(live=["activestream"])
    pb.handlers[pb.BTN_PLAYPAUSE](pb.BTN_PLAYPAUSE)
    assert player.status == "playing"
    pb.handlers[pb.BTN_PLAYPAUSE](pb.BTN_PLAYPAUSE)
    assert player.status == "stopped"


def test_skip_forward_and_back():
    c, pb, player, _ = make_controls(live=["a", "b", "c"], playing="a")
    pb.handlers[pb.BTN_FASTFWD](pb.BTN_FASTFWD)
    assert player.playing == "b"
    pb.handlers[pb.BTN_REWIND](pb.BTN_REWIND)
    assert player.playing == "a"
    # wraps around
    pb.handlers[pb.BTN_REWIND](pb.BTN_REWIND)
    assert player.playing == "c"


def test_volume_buttons():
    c, pb, player, _ = make_controls()
    pb.handlers[pb.BTN_VOLUP](pb.BTN_VOLUP)
    assert player.volume == 55
    pb.handlers[pb.BTN_VOLDN](pb.BTN_VOLDN)
    assert player.volume == 50


def test_tap_onoff_does_not_shutdown():
    c, pb, player, shutdowns = make_controls()
    pb.handlers[pb.BTN_ONOFF](pb.BTN_ONOFF)   # a tap
    assert shutdowns == []


def test_hold_onoff_shuts_down():
    c, pb, player, shutdowns = make_controls()
    pb.hold_handlers[pb.BTN_ONOFF](pb.BTN_ONOFF)  # a 3s hold
    assert shutdowns == [True]


def test_no_live_streams_is_safe():
    c, pb, player, _ = make_controls(live=[], playing="")
    pb.handlers[pb.BTN_PLAYPAUSE](pb.BTN_PLAYPAUSE)  # nothing to play
    pb.handlers[pb.BTN_FASTFWD](pb.BTN_FASTFWD)      # nothing to skip to
    assert player.status != "playing"
