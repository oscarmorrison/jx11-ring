from jx11 import RingGestureParser, decode_touch


def _run(*reports):
    out = []
    p = RingGestureParser(lambda *a: out.append(a))
    for r in reports:
        p.feed(bytes.fromhex(r))
    return out


def test_decode_touch_packs_12_bit_xy():
    assert decode_touch(bytes.fromhex("0107f4e115")) == (0x07, 500, 350)


def test_wheel_y_rising_is_scroll_back():
    assert _run("0100f4e115", "0107f4e115", "0107f4c117", "0107f4014b", "0100f42121") == [("scroll", -1)]


def test_wheel_y_falling_is_scroll_forward():
    assert _run("0107f4c126", "0107f4e124", "0107f40100", "0102f4611d") == [("scroll", 1)]


def test_left_arrow():
    assert _run("01002c411f", "01022c411f", "01072c911f", "010754411f", "010220431f") == [("left",)]


def test_right_arrow():
    assert _run("0107bc921f", "010794421f", "0102c8401f") == [("right",)]


def test_bottom_button_is_still_tap():
    assert _run("0107f40119", "0100f40119") == [("bottom",)]


def test_centre_button_is_volume_down_and_release_ignored():
    assert _run("03ea00", "030000") == [("centre",)]


def test_pulley_mode_one_scroll_per_click():
    assert _run("010fef611d", "010fef811b", "010fefa119", "010fefe11a", "010fef211c") == [
        ("scroll", 1), ("scroll", 1), ("scroll", 1), ("scroll", -1), ("scroll", -1),
    ]


def test_pulley_mode_arrows_are_button_report():
    assert _run("020040", "020000", "020080", "020000") == [("left",), ("right",)]


def test_bottom_tap_after_pulley_still_fires():
    assert _run("010fef611d", "0107f40119", "0100f40119") == [("scroll", 1), ("bottom",)]


def test_centre_alternates_volume_down_and_up():
    assert _run("03ea00", "030000", "03e900", "030000") == [("centre",), ("centre",)]


def test_centre_double_press_is_ac_home():
    assert _run("032302", "030000") == [("centre_double",)]


def test_stop_waits_for_reader_before_closing_device():
    """Closing the HID device mid-read segfaults IOKit; stop() must let the reader exit first."""
    import threading
    import time

    from jx11 import Ring

    events = []

    class FakeDev:
        def read(self, n, timeout=0):
            events.append(("read-start", threading.current_thread().name))
            time.sleep(0.3)               # a read in flight when stop() is called
            events.append(("read-end", threading.current_thread().name))
            return b""

        def close(self):
            events.append(("close", threading.current_thread().name))

    ring = Ring()
    ring._running = True
    ring._dev = FakeDev()
    ring._read_thread = threading.Thread(target=ring._read_loop, daemon=True, name="ring-read")
    ring._read_thread.start()
    time.sleep(0.1)                        # reader is now inside read()
    ring.stop()
    kinds = [k for k, _ in events]
    assert kinds.index("close") > kinds.index("read-end")
    assert not ring._read_thread.is_alive()


def test_ring_hardware_double_click_is_next_and_previous_track():
    assert _run("03b500", "030000") == [("right_double",)]
    assert _run("03b600", "030000") == [("left_double",)]
