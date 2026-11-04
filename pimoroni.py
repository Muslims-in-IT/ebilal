# -*- coding: utf-8 -*-
"""Pimoroni pHAT BEAT support: physical buttons and the 2x8 LED bar.

Buttons are read from the KERNEL, not a GPIO library. setup.sh --pimoroni adds
one `gpio-key` device-tree overlay per button, so each press arrives as an
ordinary key event on /dev/input/eventN. The kernel does the interrupts and
debouncing, which means:
  * nothing to compile, and no RPi.GPIO edge detection (broken since kernel 6.5,
    when sysfs GPIO numbering moved to start at 512);
  * no polling, so no CPU used while idle;
  * any keyboard or USB remote with media keys works too.

    button      GPIO  key code                 action
    play/pause    6   164 KEY_PLAYPAUSE        stop, or resume at the live edge
    fast-fwd      5   163 KEY_NEXTSONG         next live stream (autoplay first)
    rewind       13   165 KEY_PREVIOUSSONG     previous live stream
    vol up       16   115 KEY_VOLUMEUP         +5, repeats while held
    vol down     26   114 KEY_VOLUMEDOWN       -5, repeats while held
    on/off       12   148 KEY_PROG1            HOLD 3s to power off

On/off deliberately uses KEY_PROG1, not KEY_POWER: systemd-logind powers the
machine off the instant it sees KEY_POWER, which would turn a brushed button
into a shutdown.

The LEDs are APA102 pixels on two GPIO lines (data 23, clock 24). They are
driven here directly; the `phatbeat` library cannot be used any more because
its setup always arms button edge detection, which now fails.
"""
import glob
import logging
import os
import select
import struct
import subprocess
import threading
import time

logger = logging.getLogger("ebilal.pimoroni")

KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG = 164, 163, 165
KEY_VOLUMEUP, KEY_VOLUMEDOWN, KEY_PROG1 = 115, 114, 148
KEYS = {KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG, KEY_VOLUMEUP, KEY_VOLUMEDOWN, KEY_PROG1}

# Overlay lines for /boot/config.txt (setup.sh writes these; kept here as the
# single source of truth for the mapping).
OVERLAYS = [
    "dtoverlay=gpio-key,gpio=6,keycode=164,label=PLAYPAUSE",
    "dtoverlay=gpio-key,gpio=5,keycode=163,label=FASTFWD",
    "dtoverlay=gpio-key,gpio=13,keycode=165,label=REWIND",
    "dtoverlay=gpio-key,gpio=16,keycode=115,label=VOLUP",
    "dtoverlay=gpio-key,gpio=26,keycode=114,label=VOLDN",
    "dtoverlay=gpio-key,gpio=12,keycode=148,label=ONOFF",
]

GREEN = (0, 160, 90)
AMBER = (200, 120, 0)
BLUE = (30, 90, 220)
RED = (200, 20, 20)

# struct input_event: timeval (2 x native long), type, code, value
EVENT_FMT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)
EV_KEY = 1
KEY_UP, KEY_DOWN, KEY_REPEAT = 0, 1, 2


# --------------------------------------------------------------------- input
def find_key_devices(keys=KEYS, sys_root="/sys/class/input"):
    """/dev/input/event* devices that can send any of our key codes."""
    found = []
    word_bits = 8 * struct.calcsize("l")
    for cap in sorted(glob.glob(os.path.join(sys_root, "event*", "device", "capabilities", "key"))):
        try:
            words = open(cap).read().split()
        except OSError:
            continue
        # Hex words, most significant first; bit N set = key code N supported
        supported = set()
        for i, word in enumerate(reversed(words)):
            value = int(word, 16)
            for bit in range(word_bits):
                if value >> bit & 1:
                    supported.add(i * word_bits + bit)
        if supported & keys:
            found.append("/dev/input/" + cap.split(os.sep)[-4])
    return found


class KeyReader(threading.Thread):
    """Reads key events from input devices and hands them to `callback(code, value)`.

    Re-scans for devices every few seconds, so it copes with them appearing
    after eBilal starts, or being unplugged (USB remotes).
    """
    RESCAN_SECONDS = 5

    def __init__(self, callback, fds=None, finder=find_key_devices):
        super().__init__(name="pimoroni-keys", daemon=True)
        self.callback = callback
        self.finder = finder
        self._fixed = fds is not None
        self.fds = dict.fromkeys(fds or [], "fd")  # fd -> path
        self._halt = threading.Event()
        self._warned = False

    def stop(self):
        self._halt.set()

    def _rescan(self):
        open_paths = set(self.fds.values())
        for path in self.finder():
            if path in open_paths:
                continue
            try:
                self.fds[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
                logger.info("Buttons: listening on %s", path)
            except OSError as e:
                if not self._warned:
                    logger.error("Buttons: cannot open %s (%s). Is the service user in the 'input' group?", path, e)
                    self._warned = True
        if not self.fds and not self._warned:
            logger.warning("Buttons: no key devices found. Run setup.sh --pimoroni and reboot.")
            self._warned = True

    def run(self):
        last_scan = 0
        while not self._halt.is_set():
            if not self._fixed and time.monotonic() - last_scan > self.RESCAN_SECONDS:
                self._rescan()
                last_scan = time.monotonic()
            if not self.fds:
                self._halt.wait(1)
                continue
            try:
                ready, _, _ = select.select(list(self.fds), [], [], 1)
            except (OSError, ValueError):
                ready = []
            for fd in ready:
                try:
                    data = os.read(fd, EVENT_SIZE * 32)
                except OSError:
                    data = b""
                if not data:  # device went away
                    logger.info("Buttons: %s disconnected", self.fds.pop(fd, fd))
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    continue
                for i in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, etype, code, value = struct.unpack(EVENT_FMT, data[i:i + EVENT_SIZE])
                    if etype == EV_KEY and code in KEYS:
                        try:
                            self.callback(code, value)
                        except Exception:
                            logger.exception("Buttons: handler for key %s failed", code)


# ---------------------------------------------------------------------- LEDs
class NoLeds:
    """Stand-in when the LEDs cannot be driven (not a Pi, no GPIO access)."""
    def set_pixel(self, *a, **k): pass
    def set_all(self, *a, **k): pass
    def clear(self): pass
    def show(self): pass


class PhatBeatLeds:
    """APA102 driver for the pHAT BEAT's 16 pixels (two columns of 8).

    Protocol and pixel order follow Pimoroni's phatbeat library (MIT licence):
    channel 0 is the left column bottom-to-top, channel 1 the right column.
    """
    DAT, CLK = 23, 24
    NUM_PIXELS, CHANNEL_PIXELS = 16, 8

    def __init__(self, gpio=None):
        if gpio is None:
            import RPi.GPIO as gpio  # outputs still work on 6.x kernels
        self.gpio = gpio
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        gpio.setup(self.DAT, gpio.OUT)
        gpio.setup(self.CLK, gpio.OUT)
        self.pixels = [[0, 0, 0, 7] for _ in range(self.NUM_PIXELS)]
        self._lock = threading.Lock()

    def set_pixel(self, x, r, g, b, brightness=0.2, channel=None):
        if channel in (0, 1):
            x += channel * self.CHANNEL_PIXELS
        if x >= self.CHANNEL_PIXELS:  # right column runs the other way
            x = self.NUM_PIXELS - 1 - (x - self.CHANNEL_PIXELS)
        self.pixels[x] = [int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF, int(31 * brightness) & 0x1F]

    def set_all(self, r, g, b, brightness=0.2):
        for x in range(self.NUM_PIXELS):
            self.pixels[x] = [int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF, int(31 * brightness) & 0x1F]

    def clear(self):
        for p in self.pixels:
            p[0:3] = [0, 0, 0]

    def _clock(self, n):
        out = self.gpio.output
        for _ in range(n):
            out(self.CLK, 1)
            out(self.CLK, 0)

    def _byte(self, byte):
        out = self.gpio.output
        for _ in range(8):
            out(self.DAT, byte & 0x80)
            out(self.CLK, 1)
            out(self.CLK, 0)
            byte <<= 1

    def show(self):
        with self._lock:
            self.gpio.output(self.DAT, 0)
            self._clock(32)                    # start frame
            for r, g, b, br in self.pixels:
                self._byte(0xE0 | br)
                self._byte(b)
                self._byte(g)
                self._byte(r)
            self.gpio.output(self.DAT, 1)
            self._clock(32)                    # end frame (latches the small APA102s)


# ------------------------------------------------------------------ controls
def _poweroff():
    subprocess.run(["sudo", "-n", "systemctl", "poweroff"], check=False)


class PhatBeatControls:
    VOLUME_STEP = 5
    REPEAT_DELAY = 0.5        # s held before volume starts repeating
    REPEAT_INTERVAL = 0.15    # s between repeats
    SHUTDOWN_HOLD = 3.0       # s the on/off button must be held
    LED_SECONDS = 1.2
    LED_BRIGHTNESS = 0.1

    def __init__(self, player, leds=None, shutdown=None, reader_factory=KeyReader):
        self.player = player
        self.leds = leds
        self._shutdown = shutdown or _poweroff
        self._reader_factory = reader_factory
        self.reader = None
        self._held = {}           # key code -> threading.Event set on release
        self._led_lock = threading.Lock()
        self._led_timer = None

    def start(self):
        if self.leds is None:
            try:
                self.leds = PhatBeatLeds()
            except Exception as e:
                logger.warning("pHAT BEAT LEDs unavailable: %s", e)
                self.leds = NoLeds()
        self.reader = self._reader_factory(self.handle_key)
        self.reader.start()
        logger.info("pHAT BEAT controls enabled")
        self._flash(GREEN)
        return self

    # ------------------------------------------------------------ key events
    def handle_key(self, code, value):
        if value == KEY_REPEAT:      # we time holds ourselves
            return
        if value == KEY_UP:
            released = self._held.pop(code, None)
            if released:
                released.set()
            return

        # KEY_DOWN
        if code == KEY_PLAYPAUSE:
            result = self.player.toggle()
            logger.info("Play/pause -> %s", result)
            self._flash(RED if result is None else AMBER if result == "stopped" else GREEN)
        elif code in (KEY_NEXTSONG, KEY_PREVIOUSSONG):
            direction = 1 if code == KEY_NEXTSONG else -1
            target = self.player.step(direction)
            logger.info("Skip %+d -> %s", direction, target)
            self._flash(RED if target is None else BLUE)
        elif code in (KEY_VOLUMEUP, KEY_VOLUMEDOWN):
            delta = self.VOLUME_STEP if code == KEY_VOLUMEUP else -self.VOLUME_STEP
            self._volume(delta)
            self._while_held(code, self.REPEAT_DELAY, lambda: self._volume(delta), repeat=True)
        elif code == KEY_PROG1:
            self._while_held(code, self.SHUTDOWN_HOLD, self._do_shutdown, repeat=False)

    def _while_held(self, code, delay, action, repeat):
        """Run `action` after `delay` if the key is still down (and then every
        REPEAT_INTERVAL if `repeat`), stopping when it is released."""
        old = self._held.pop(code, None)
        if old:
            old.set()
        released = threading.Event()
        self._held[code] = released

        def loop():
            wait = delay
            while not released.wait(wait):
                try:
                    action()
                except Exception:
                    logger.exception("Held-key action failed")
                if not repeat:
                    return
                wait = self.REPEAT_INTERVAL

        threading.Thread(target=loop, name="pimoroni-hold", daemon=True).start()

    def _volume(self, delta):
        level = self.player.nudge_volume(delta)
        self._show_bar(level)

    def _do_shutdown(self):
        logger.warning("On/off held for %ss, powering off", self.SHUTDOWN_HOLD)
        self._flash(RED)
        self._shutdown()

    # ------------------------------------------------------------------ LEDs
    def _show_bar(self, volume):
        lit = round(volume / 100 * 8)
        colour = GREEN if volume < 80 else AMBER
        with self._led_lock:
            self.leds.clear()
            for channel in (0, 1):
                for x in range(lit):
                    self.leds.set_pixel(x, *colour, brightness=self.LED_BRIGHTNESS, channel=channel)
            self.leds.show()
        self._clear_soon()

    def _flash(self, colour):
        with self._led_lock:
            self.leds.set_all(*colour, brightness=self.LED_BRIGHTNESS)
            self.leds.show()
        self._clear_soon()

    def _clear_soon(self):
        if self._led_timer is not None:
            self._led_timer.cancel()
        self._led_timer = threading.Timer(self.LED_SECONDS, self._clear)
        self._led_timer.daemon = True
        self._led_timer.start()

    def _clear(self):
        with self._led_lock:
            self.leds.clear()
            self.leds.show()
