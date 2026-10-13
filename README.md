# jx11-ring

Python driver and protocol notes for the **JX-11 Bluetooth scroll ring**
(sold as "Plyisty Scrolling Ring" and similar white-label names).

It poses as an Apple keyboard with a fake touchscreen, and almost nothing is
documented online. This repo records how it talks, plus a small driver that
turns raw HID reports into clean events: `scroll`, `centre`, `centre_double`,
`left`, `right`, `left_double`, `right_double`, `bottom`.

See [PROTOCOL.md](PROTOCOL.md) for the report formats.

## Use

```sh
pip install hidapi
python examples/events.py     # high-level events
python examples/dump.py       # raw reports
```

```python
from jx11 import Ring

ring = Ring()
ring.on("scroll", lambda steps: print(steps))   # +1 forward, -1 back
ring.on("centre", lambda: print("centre"))
ring.start()
```

## Status
- Tested on macOS with one unit. Linux/Windows untested.
- Put the ring in **pulley** mode first (hold ◀ + ▶ for 3 s to cycle modes).
- Other units may use a different VID/PID. Run `examples/dump.py` and open an issue with what you see.

## Tests
```sh
pip install pytest && pytest
```

MIT licensed.
