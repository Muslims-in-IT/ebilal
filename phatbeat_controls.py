# -*- coding: utf-8 -*-
"""Physical controls for the Pimoroni pHAT BEAT (Pirate Radio kit).

Buttons
    play/pause   stop the stream, or resume the last one at the live edge
    fast-fwd     next live stream (pinned feeds first)
    rewind       previous live stream
    vol up/down  +/-5, auto-repeats while held, applied once the button settles
    on/off       HOLD for 3 seconds to shut the Pi down (a tap does nothing)

The LEDs give feedback: a volume bar, a green/amber flash for play/stop, a blue
flash for skip, and red when there is nothing live to play.

The `phatbeat` module is injectable so the logic can be tested without a Pi.
"""
import logging
import os
import threading
import time

logger = logging.getLogger("ebilal.pimoroni")

GREEN = (0, 160, 90)
AMBER = (200, 120, 0)
BLUE = (30, 90, 220)
RED = (200, 20, 20)


class PhatBeatControls:
    VOLUME_STEP = 5
    REPEAT_MIN_INTERVAL = 0.12   # s; GPIO auto-repeat ramps up to 100/s, far too fast
    SHUTDOWN_HOLD_SECONDS = 3
    LED_SECONDS = 1.2
    LED_BRIGHTNESS = 0.1

    def __init__(self, player, phatbeat=None, shutdown=None):
        self.player = player
        self._pb = phatbeat
        self._shutdown = shutdown or (lambda: os.system("sudo shutdown -h now"))
        self._led_lock = threading.Lock()
        self._led_timer = None
        self._last_repeat = {}

    # ------------------------------------------------------------------ setup
    def start(self):
        if self._pb is None:
            import phatbeat  # needs RPi.GPIO and access to /dev/gpiomem
            self._pb = phatbeat
        pb = self._pb
        logger.info("Phatbeat found, enabling buttons")

        pb.on(pb.BTN_PLAYPAUSE, self.on_play_pause, repeat=False)
        pb.on(pb.BTN_FASTFWD, self.on_next, repeat=False)
        pb.on(pb.BTN_REWIND, self.on_prev, repeat=False)
        pb.on(pb.BTN_VOLUP, self.on_volume_up, repeat=True)
        pb.on(pb.BTN_VOLDN, self.on_volume_down, repeat=True)
        # Shutdown only on a deliberate hold; a tap runs the no-op below
        pb.on(pb.BTN_ONOFF, lambda pin: None, repeat=False)
        pb.hold(pb.BTN_ONOFF, self.on_shutdown, repeat=False,
                hold_time=self.SHUTDOWN_HOLD_SECONDS)

        self._flash(GREEN)

    # --------------------------------------------------------------- handlers
    def _guard(self, name, fn):
        """GPIO callbacks run on a library thread; an exception there is silent."""
        try:
            fn()
        except Exception:
            logger.exception("Button handler '%s' failed", name)

    def on_play_pause(self, pin=None):
        def go():
            result = self.player.toggle()
            logger.info("Play/pause pressed -> %s", result)
            self._flash(RED if result is None else AMBER if result == "stopped" else GREEN)
        self._guard("play/pause", go)

    def on_next(self, pin=None):
        self._guard("next", lambda: self._skip(+1))

    def on_prev(self, pin=None):
        self._guard("prev", lambda: self._skip(-1))

    def _skip(self, direction):
        target = self.player.step(direction)
        logger.info("Skip %+d -> %s", direction, target)
        self._flash(RED if target is None else BLUE)

    def on_volume_up(self, pin=None):
        self._guard("volume up", lambda: self._volume(+self.VOLUME_STEP, pin))

    def on_volume_down(self, pin=None):
        self._guard("volume down", lambda: self._volume(-self.VOLUME_STEP, pin))

    def _volume(self, delta, pin):
        now = time.monotonic()
        if now - self._last_repeat.get(pin, 0) < self.REPEAT_MIN_INTERVAL:
            return
        self._last_repeat[pin] = now
        level = self.player.nudge_volume(delta)
        logger.debug("Volume -> %s", level)
        self._show_bar(level)

    def on_shutdown(self, pin=None):
        logger.warning("On/off held for %ss, shutting down", self.SHUTDOWN_HOLD_SECONDS)
        self._flash(RED)
        self._guard("shutdown", self._shutdown)

    # -------------------------------------------------------------------- LEDs
    def _show_bar(self, volume):
        """Volume as a bar across both 8-LED channels."""
        lit = round(volume / 100 * 8)
        colour = GREEN if volume < 80 else AMBER
        with self._led_lock:
            pb = self._pb
            pb.clear()
            for channel in (0, 1):
                for x in range(lit):
                    pb.set_pixel(x, *colour, brightness=self.LED_BRIGHTNESS, channel=channel)
            pb.show()
        self._clear_soon()

    def _flash(self, colour):
        with self._led_lock:
            pb = self._pb
            pb.set_all(*colour, brightness=self.LED_BRIGHTNESS)
            pb.show()
        self._clear_soon()

    def _clear_soon(self):
        if self._led_timer is not None:
            self._led_timer.cancel()
        self._led_timer = threading.Timer(self.LED_SECONDS, self._clear)
        self._led_timer.daemon = True
        self._led_timer.start()

    def _clear(self):
        with self._led_lock:
            self._pb.clear()
            self._pb.show()
