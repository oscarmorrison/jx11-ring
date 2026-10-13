"""
JX-11 Bluetooth scroll ring driver for macOS.

The ring (sold as "Plyisty Scrolling Ring" and similar) pretends to be an
Apple keyboard (VID 0x05AC / PID 0x0220) with a fake touchscreen.

  Report 0x01 — digitizer: [01, flags, x lo, x hi | y lo, y hi]
      flags & 0x01 = finger down, flags & 0x08 = "pulley" (finger held,
      nudged one step per wheel click); x/y are 12-bit packed
  Report 0x02 — buttons: [02, 00, bitmap]  0x40 = right, 0x80 = left (as worn)
  Report 0x03 — consumer control: [03, usage lo, usage hi]  (0 = release)

Names below are as worn: wheel at the bottom; middle oval; small top circle;
left and right buttons. (The ring's own firmware calls left and right the other
way round — it expects to be worn the other way up.)

Holding left + right for 3 s cycles the ring's modes (blue LED stays on 5 s).
Use the "pulley" mode — it's the only one where every button is distinct:

  Wheel         → pulley frame per click, Y falling / rising
  Left / Right  → report 0x02 bits 0x80 / 0x40
  Middle        → Volume Down (0xEA) / Volume Up (0xE9), alternating
  Middle ×2     → AC Home (0x0223) — one event, no single-press events
  Left ×2       → Next Track (0xB5), Right ×2 → Previous Track (0xB6) — the ring's own
                  double-click: one event, with no single-press events before it
  Top           → tap with no movement

The swipe mode (wheel = vertical swipe, left/right = horizontal swipes) is also
understood. In the third mode the wheel sends the same swipes as left/right, so
they can't be told apart — switch modes if the wheel deletes words.

The device is opened exclusively (IOHIDDevice seize), so macOS never sees
these events — no volume changes, no fake clicks.

Events (same .on() shape as Tiller):
  ring.on('scroll', lambda steps: ...)  # +1 forward, -1 back, one per wheel click
  ring.on('middle' | 'middle_double' | 'top' | 'left' | 'right' | 'left_double' | 'right_double', handler)
  ring.on('connect' | 'disconnect', handler)
"""

import hid
import threading
import logging

log = logging.getLogger(__name__)

VENDOR_ID    = 0x05AC
PRODUCT_ID   = 0x0220
# The ring exposes two HID collections; the Consumer page (0x0C) one carries
# every report. Match on that rather than the name, which macOS lets you change.
USAGE_PAGE_CONSUMER = 0x0C

REPORT_TOUCH    = 0x01
REPORT_BUTTONS  = 0x02
REPORT_CONSUMER = 0x03
USAGE_VOLUME_DOWN = 0x00EA
USAGE_VOLUME_UP   = 0x00E9
USAGE_AC_HOME     = 0x0223   # the ring sends this for a middle double-press
USAGE_NEXT_TRACK  = 0x00B5   # left-button double-click (the ring's own double-click detection)
USAGE_PREV_TRACK  = 0x00B6   # right-button double-click
BUTTON_RIGHT = 0x40   # as worn (the firmware calls this one left)
BUTTON_LEFT  = 0x80
FLAG_DOWN   = 0x01
FLAG_PULLEY = 0x08
# Where the pulley finger rests before the first wheel click.
PULLEY_ORIGIN_Y = 500

# Positions move ~30 units per frame during a swipe; anything smaller is jitter.
MOVE_THRESHOLD = 15
RECONNECT_INTERVAL = 2.0   # seconds between looks for the ring while it's absent

try:
    # Seize the device so macOS doesn't also act on it. hidapi ≥0.12 already
    # defaults to exclusive; be explicit in case that ever changes.
    hid.hidapi.hid_darwin_set_open_exclusive(1)
except AttributeError:
    pass


def decode_touch(data) -> tuple[int, int, int]:
    """Return (flags, x, y) for a 0x01 touch report."""
    x = data[2] | ((data[3] & 0x0F) << 8)
    y = (data[3] >> 4) | (data[4] << 4)
    return data[1], x, y


def classify_move(start: tuple[int, int], pos: tuple[int, int]) -> tuple | None:
    """Map movement from the touch-down point to the event to emit, or None if still."""
    dx = pos[0] - start[0]
    dy = pos[1] - start[1]
    if max(abs(dx), abs(dy)) < MOVE_THRESHOLD:
        return None
    if abs(dy) >= abs(dx):
        return ("scroll", 1 if dy < 0 else -1)
    return ("right",) if dx > 0 else ("left",)   # worn with the wheel at the bottom


class RingGestureParser:
    """Turns raw reports into button events. Pure — no I/O, easy to test."""

    def __init__(self, emit):
        self._emit = emit
        self._start: tuple[int, int] | None = None
        self._last: tuple[int, int] | None = None
        self._fired = False
        self._pulley_y: int | None = None

    def reset(self):
        self._start = None
        self._last = None
        self._fired = False
        self._pulley_y = None

    def feed(self, data):
        if not data:
            return
        if data[0] == REPORT_CONSUMER and len(data) >= 3:
            usage = data[1] | (data[2] << 8)
            # The middle button alternates Volume Down / Volume Up on each press.
            if usage in (USAGE_VOLUME_DOWN, USAGE_VOLUME_UP):
                self._emit("middle")
            elif usage == USAGE_AC_HOME:
                self._emit("middle_double")
            elif usage == USAGE_NEXT_TRACK:
                self._emit("left_double")
            elif usage == USAGE_PREV_TRACK:
                self._emit("right_double")
            elif usage:
                log.debug(f"ring: unmapped consumer usage {usage:#06x}")
            return
        if data[0] != REPORT_TOUCH:   # touch frames are far too frequent to log; everything else is one per press
            log.debug(f"ring report: {bytes(data).hex(' ')}")
        if data[0] == REPORT_BUTTONS and len(data) >= 3:
            if data[2] & BUTTON_LEFT:
                self._emit("left")
            elif data[2] & BUTTON_RIGHT:
                self._emit("right")
            return
        if data[0] != REPORT_TOUCH or len(data) < 5:
            return

        flags, x, y = decode_touch(data)
        if flags & FLAG_PULLEY:
            # One frame per wheel click; direction is the step from the last one.
            prev = PULLEY_ORIGIN_Y if self._pulley_y is None else self._pulley_y
            self._pulley_y = y
            if abs(y - prev) >= MOVE_THRESHOLD:
                self._emit("scroll", 1 if y < prev else -1)
            return

        if flags & FLAG_DOWN:
            self._last = (x, y)
            if self._start is None:
                self._start = (x, y)
                self._fired = False
            elif not self._fired:
                # Fire on the first real movement for low latency; the frames
                # around lift-off carry junk positions, so ignore the rest.
                event = classify_move(self._start, (x, y))
                if event:
                    self._fired = True
                    self._emit(*event)
            return

        self._pulley_y = None
        if self._start is not None:
            log.debug(f"ring touch: {self._start} → {self._last} fired={self._fired}")
            if not self._fired:
                self._emit("top")
            self.reset()


class Ring:
    def __init__(self):
        self._handlers: dict[str, list] = {}
        self._dev: hid.Device | None = None
        self._running = False
        self._reconnect_timer: threading.Timer | None = None
        self._logged_absent = False
        self._read_thread: threading.Thread | None = None
        self._parser = RingGestureParser(self._emit)

    def on(self, event: str, handler) -> "Ring":
        self._handlers.setdefault(event, []).append(handler)
        return self

    def start(self):
        self._running = True
        self._connect_once()

    def stop(self):
        self._running = False
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
        # Closing the device while the reader is mid-read segfaults IOKit, so let
        # the reader (read timeout 0.5 s) notice _running is False and exit first.
        t = self._read_thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2)
            if t.is_alive():
                return   # leak the handle rather than crash
        self._close_dev()

    @property
    def connected(self) -> bool:
        return self._dev is not None

    def _close_dev(self):
        if self._dev:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None

    def _emit(self, event: str, *args):
        if event not in ("connect", "disconnect"):
            log.info(f"ring button: {event}{args if args else ''}")   # one line per press, not per frame
        for handler in self._handlers.get(event, []):
            try:
                handler(*args)
            except Exception as e:
                log.exception(f"ring handler error for '{event}': {e}")

    def _find_path(self):
        for info in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if info.get("usage_page") == USAGE_PAGE_CONSUMER:
                return info["path"]
        return None

    def _connect_once(self):
        if self._dev is not None or not self._running:
            return
        try:
            path = self._find_path()
            if path is None:
                raise IOError("JX-11 not paired/awake")
            self._dev = hid.Device(path=path)
        except Exception as e:
            if not self._logged_absent:   # once, not every retry
                log.info(f"Ring not available, will keep looking: {e}")
                self._logged_absent = True
            self._schedule_reconnect()
            return
        log.info("Ring connected (seized)")
        self._logged_absent = False
        self._parser.reset()
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True, name="ring-read")
        self._read_thread.start()
        self._emit("connect")

    def _schedule_reconnect(self):
        if not self._running:
            return
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
        self._reconnect_timer = threading.Timer(RECONNECT_INTERVAL, self._connect_once)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _read_loop(self):
        while self._running and self._dev:
            try:
                data = self._dev.read(64, timeout=500)
                if data:
                    self._parser.feed(data)
            except Exception as e:
                log.warning(f"Ring read error (asleep/disconnected?): {e}")
                self._close_dev()
                self._parser.reset()
                self._emit("disconnect")
                self._schedule_reconnect()
                return
