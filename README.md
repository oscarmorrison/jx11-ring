# jx11-ring

Python driver and protocol notes for the **JX-11 Bluetooth scroll ring**
(sold as "Plyisty Scrolling Ring" and similar white-label names).

It poses as an Apple keyboard with a fake touchscreen, and almost nothing is
documented online. This repo records how it talks, plus a small driver that
turns raw HID reports into clean events: `scroll`, `centre`, `centre_double`,
`left`, `right`, `left_double`, `right_double`, `bottom`.

See [PROTOCOL.md](PROTOCOL.md) for the report formats.

## Get one
[Buy the ring on Amazon](https://link.amazon/B0fpmzGvn) (**affiliate link**: I earn a small commission at no extra cost to you).

## Set it up with your AI agent
Paste this into Claude Code, Codex or similar:

```text
Set up the JX-11 Bluetooth scroll ring using https://github.com/oscarmorrison/jx11-ring

1. Clone the repo and run `pip install hidapi` (use a venv).
2. Read PROTOCOL.md, then run `python examples/dump.py` and ask me to press each button and turn the wheel, to confirm my unit matches (VID 0x05AC, PID 0x0220). If it doesn't, tell me what you see.
3. Run `python examples/events.py` and confirm scroll, centre, left, right and double-press events fire.
4. Then wire the ring into my project: import `Ring` from jx11, register handlers with `ring.on(...)`, and call `ring.start()`. Ask me what each button should do.
```

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
