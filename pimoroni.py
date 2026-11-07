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
import array
import glob
import logging
import math
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

# LED colour schemes for the VU meter and the volume bar: one colour per
# position, bottom (0) to top (7). Shown as swatches in the web UI.
def _ramp(a, b, n=8):
    return [tuple(round(a[c] + (b[c] - a[c]) * i / (n - 1)) for c in range(3)) for i in range(n)]

SCHEMES = {
    "classic": [(0, 170, 60)] * 5 + [(210, 140, 0)] * 2 + [(220, 20, 20)],   # green, amber, red
    "ebilal":  _ramp((15, 160, 140), (212, 175, 89)),                        # app teal to gold
    "ocean":   _ramp((0, 40, 200), (40, 220, 230)),                          # deep blue to cyan
    "sunset":  _ramp((230, 150, 0), (210, 20, 80)),                          # amber to magenta
    "rainbow": [(220, 20, 20), (230, 100, 0), (220, 190, 0), (40, 190, 40),
                (0, 170, 170), (20, 90, 230), (110, 40, 220), (190, 40, 190)],
    "white":   [(200, 200, 200)] * 8,
}
DEFAULT_SCHEME = "classic"

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
    channel 0 is the left column, channel 1 the right, position 0 at the
    "bottom" when the board is mounted Pimoroni's way. In the Pirate Radio case
    the board sits the other way up, so `flip` (default) makes position 0 the
    physical bottom there.
    """
    DAT, CLK = 23, 24
    NUM_PIXELS, CHANNEL_PIXELS = 16, 8
    # MSB-first data bits for every byte value, precomputed for show()
    _BITS = [tuple((b >> i) & 1 for i in range(7, -1, -1)) for b in range(256)]

    def __init__(self, gpio=None, flip=True):
        if gpio is None:
            import RPi.GPIO as gpio  # outputs still work on 6.x kernels
        self.gpio = gpio
        self.flip = flip
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        gpio.setup(self.DAT, gpio.OUT)
        gpio.setup(self.CLK, gpio.OUT)
        self.pixels = [[0, 0, 0, 7] for _ in range(self.NUM_PIXELS)]
        self._lock = threading.Lock()

    def _index(self, x, channel):
        if channel in (0, 1):
            col, pos = channel, x
        else:
            col, pos = divmod(x, self.CHANNEL_PIXELS)
        if not 0 <= pos < self.CHANNEL_PIXELS:
            raise IndexError("LED position %s out of range" % x)
        if self.flip:
            pos = self.CHANNEL_PIXELS - 1 - pos
        # The chain runs up the left column and back down the right one
        return pos if col == 0 else self.NUM_PIXELS - 1 - pos

    def set_pixel(self, x, r, g, b, brightness=0.2, channel=None):
        self.pixels[self._index(x, channel)] = [int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF,
                                                 int(31 * brightness) & 0x1F]

    def set_all(self, r, g, b, brightness=0.2):
        for x in range(self.NUM_PIXELS):
            self.pixels[x] = [int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF, int(31 * brightness) & 0x1F]

    def clear(self):
        for p in self.pixels:
            p[0:3] = [0, 0, 0]

    def show(self):
        """Clock out one frame: 32 zero bits, 4 bytes per pixel, 32 one bits.
        Data and clock-high go out in one call (about 12 ms a frame on a Zero)."""
        frame = bytearray(4)
        for r, g, b, br in self.pixels:
            frame += bytes((0xE0 | br, b, g, r))
        frame += b"\xff" * 4
        out, pair, clk, bits = self.gpio.output, [self.DAT, self.CLK], self.CLK, self._BITS
        with self._lock:
            for byte in frame:
                for bit in bits[byte]:
                    out(pair, (bit, 1))
                    out(clk, 0)


# ----------------------------------------------------------------- VU meter
class VuMeter:
    """Stereo level meter on the LED columns, fed by the player.

    The player (ffmpeg) writes a low-rate copy of the audio, 16-bit stereo at
    RATE Hz, to a pipe. attach(pipe) starts a thread that MUST keep draining it
    (a full pipe would stall the audio), turns each 1/FPS second into an RMS
    level per channel, and lights 0..8 LEDs per column. Redraws only when the
    bars change, and stays out of the way while button feedback is showing.
    """
    RATE = 2000
    FPS = 10
    FLOOR_DB = -40.0       # level shown as zero LEDs
    PEAK_DECAY = 1         # LEDs dropped per frame, so peaks fall smoothly
    BRIGHTNESS = 0.08

    def __init__(self, leds, lock, busy=lambda: False, scheme=DEFAULT_SCHEME, brightness=None):
        self.leds = leds
        self.lock = lock
        self.busy = busy
        self.scheme = scheme if scheme in SCHEMES else DEFAULT_SCHEME
        if brightness is not None:
            self.BRIGHTNESS = brightness
        self._gen = 0
        self._gen_lock = threading.Lock()

    def attach(self, pipe):
        with self._gen_lock:
            self._gen += 1
            gen = self._gen
        threading.Thread(target=self._run, args=(pipe, gen), name="pimoroni-vu", daemon=True).start()

    def level(self, samples):
        """RMS of int16 samples -> LEDs lit, 0..8."""
        if not samples:
            return 0
        rms = math.sqrt(sum(x * x for x in samples) / len(samples))
        if rms < 1:
            return 0
        db = 20 * math.log10(rms / 32768.0)
        return max(0, min(8, round((db - self.FLOOR_DB) / -self.FLOOR_DB * 8)))

    def colour(self, i):
        return SCHEMES.get(self.scheme, SCHEMES[DEFAULT_SCHEME])[i]

    def _draw(self, left, right):
        with self.lock:
            self.leds.clear()
            for channel, lit in ((0, left), (1, right)):
                for x in range(lit):
                    self.leds.set_pixel(x, *self.colour(x), brightness=self.BRIGHTNESS, channel=channel)
            self.leds.show()

    def _run(self, pipe, gen):
        chunk = self.RATE // self.FPS * 4          # frames per tick x 2 channels x 2 bytes
        shown = (0, 0)
        try:
            while True:
                data = pipe.read(chunk)
                if not data:
                    break
                if gen != self._gen:
                    continue                       # a newer stream took over: just drain
                data = data[: len(data) // 4 * 4]
                pcm = array.array("h", data)
                target = (self.level(pcm[0::2]), self.level(pcm[1::2]))
                # instant rise, gentle fall
                new = tuple(max(t, s - self.PEAK_DECAY) for t, s in zip(target, shown))
                if new != shown and not self.busy():
                    self._draw(*new)
                shown = new
        except (OSError, ValueError):
            pass
        finally:
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
            if gen == self._gen and not self.busy():
                self._draw(0, 0)


# ------------------------------------------------------------------ controls
def _poweroff():
    subprocess.run(["sudo", "-n", "systemctl", "poweroff"], check=False)


class PhatBeatControls:
    VOLUME_STEP = 5
    REPEAT_DELAY = 0.5        # s held before volume starts repeating
    REPEAT_INTERVAL = 0.15    # s between repeats
    SHUTDOWN_HOLD = 3.0       # s the on/off button must be held
    LED_SECONDS = 1.2

    def __init__(self, player, leds=None, shutdown=None, reader_factory=KeyReader,
                 flip=True, vu_meter=True, scheme=DEFAULT_SCHEME, brightness=10, boot_animation=True):
        self.player = player
        self.leds = leds
        self.flip = flip
        self.vu_meter = vu_meter
        self.scheme = scheme if scheme in SCHEMES else DEFAULT_SCHEME
        self.LED_BRIGHTNESS = max(1, min(100, int(brightness))) / 100.0
        self.boot_animation = boot_animation
        self.vu = None
        self._busy_until = 0.0
        self._shutdown = shutdown or _poweroff
        self._reader_factory = reader_factory
        self.reader = None
        self._held = {}           # key code -> threading.Event set on release
        self._led_lock = threading.Lock()
        self._led_timer = None

    def start(self):
        if self.leds is None:
            try:
                self.leds = PhatBeatLeds(flip=self.flip)
            except Exception as e:
                logger.warning("pHAT BEAT LEDs unavailable: %s", e)
                self.leds = NoLeds()
        if not isinstance(self.leds, NoLeds):
            self.leds.flip = self.flip
            self.vu = VuMeter(self.leds, self._led_lock, busy=self.busy,
                              scheme=self.scheme, brightness=self.LED_BRIGHTNESS)
            if self.vu_meter:
                self.player.vu_sink = self.vu.attach   # player sends it a low-rate audio copy
                logger.info("VU meter enabled")
        self.reader = self._reader_factory(self.handle_key)
        self.reader.start()
        logger.info("pHAT BEAT controls enabled")
        if self.boot_animation:
            threading.Thread(target=self.kitt, name="pimoroni-kitt", daemon=True).start()
        else:
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

    # -------------------------------------------------------------- settings
    def settings(self):
        return {"vu_meter": self.vu_meter, "led_flip": self.flip, "boot_animation": self.boot_animation, "led_scheme": self.scheme,
                "led_brightness": round(self.LED_BRIGHTNESS * 100),
                "leds_available": not isinstance(self.leds, NoLeds)}

    def apply(self, vu_meter=None, led_flip=None, led_scheme=None, led_brightness=None,
              boot_animation=None):
        """Change settings live. Returns True if the playing stream must restart
        (switching the VU meter changes how the player is launched)."""
        restart = False
        if boot_animation is not None:
            self.boot_animation = bool(boot_animation)
        if led_flip is not None:
            self.flip = bool(led_flip)
            self.leds.flip = self.flip
        if led_scheme is not None:
            if led_scheme not in SCHEMES:
                raise ValueError("unknown colour scheme: %s" % led_scheme)
            self.scheme = led_scheme
            if self.vu:
                self.vu.scheme = led_scheme
        if led_brightness is not None:
            self.LED_BRIGHTNESS = max(1, min(100, int(led_brightness))) / 100.0
            if self.vu:
                self.vu.BRIGHTNESS = self.LED_BRIGHTNESS
        if vu_meter is not None and bool(vu_meter) != self.vu_meter:
            self.vu_meter = bool(vu_meter)
            if self.vu:
                self.player.vu_sink = self.vu.attach if self.vu_meter else None
                restart = True
        return restart

    def kitt(self, sweeps=2, frame=0.045):
        """KITT scanner: a red eye with a fading tail sweeps up and down both
        columns, then a flash in the current scheme. Runs at boot."""
        tail = (1.0, 0.45, 0.18, 0.06)              # brightness of the eye and its tail
        path = list(range(8)) + list(range(6, 0, -1))  # up, then back down
        self._busy_until = time.monotonic() + sweeps * len(path) * (frame + 0.012) + 1.5
        trail = []
        for _ in range(sweeps):
            for pos in path:
                trail = [pos] + trail[:len(tail) - 1]
                with self._led_lock:
                    self.leds.clear()
                    for age, x in reversed(list(enumerate(trail))):
                        level = tail[age]
                        for channel in (0, 1):
                            self.leds.set_pixel(x, round(255 * level), 0, 0,
                                                brightness=self.LED_BRIGHTNESS, channel=channel)
                    self.leds.show()
                time.sleep(frame)
        colours = SCHEMES[self.scheme]
        with self._led_lock:
            self.leds.clear()
            for channel in (0, 1):
                for x in range(8):
                    self.leds.set_pixel(x, *colours[x], brightness=self.LED_BRIGHTNESS, channel=channel)
            self.leds.show()
        time.sleep(0.6)
        self._clear()

    def test_leds(self):
        """Fill both columns bottom to top in the current scheme, then clear:
        shows direction, colours and brightness in about two seconds."""
        def run():
            self._busy_until = time.monotonic() + 3
            colours = SCHEMES[self.scheme]
            for lit in range(1, 9):
                with self._led_lock:
                    self.leds.clear()
                    for channel in (0, 1):
                        for x in range(lit):
                            self.leds.set_pixel(x, *colours[x], brightness=self.LED_BRIGHTNESS, channel=channel)
                    self.leds.show()
                time.sleep(0.18)
            time.sleep(0.8)
            self._clear()
        threading.Thread(target=run, name="pimoroni-test", daemon=True).start()

    # ------------------------------------------------------------------ LEDs
    def busy(self):
        """True while button feedback owns the LEDs (the VU meter waits)."""
        return time.monotonic() < self._busy_until

    def _show_bar(self, volume):
        lit = round(volume / 100 * 8)
        colours = SCHEMES[self.scheme]
        with self._led_lock:
            self.leds.clear()
            for channel in (0, 1):
                for x in range(lit):
                    self.leds.set_pixel(x, *colours[x], brightness=self.LED_BRIGHTNESS, channel=channel)
            self.leds.show()
        self._clear_soon()

    def _flash(self, colour):
        with self._led_lock:
            self.leds.set_all(*colour, brightness=self.LED_BRIGHTNESS)
            self.leds.show()
        self._clear_soon()

    def _clear_soon(self):
        self._busy_until = time.monotonic() + self.LED_SECONDS
        if self._led_timer is not None:
            self._led_timer.cancel()
        self._led_timer = threading.Timer(self.LED_SECONDS, self._clear)
        self._led_timer.daemon = True
        self._led_timer.start()

    def _clear(self):
        with self._led_lock:
            self.leds.clear()
            self.leds.show()
