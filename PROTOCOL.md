# JX-11 protocol notes

Reverse-engineered from one unit on macOS. Other units may differ.

## Identity
- Advertises as an Apple keyboard: VID `0x05AC`, PID `0x0220`.
- Two HID collections; the Consumer page (`0x0C`) one carries every report.
  Match on that, not the name (macOS lets you rename the device).

## Reports
| ID | Meaning | Layout |
|----|---------|--------|
| `0x01` | Fake touchscreen digitizer | `[01, flags, x lo, x hi\|y lo, y hi]`, x/y 12-bit packed |
| `0x02` | Arrow buttons | `[02, 00, bitmap]`, `0x40` = ◀, `0x80` = ▶ |
| `0x03` | Consumer control | `[03, usage lo, usage hi]`, usage 0 = release |

Digitizer flags: `0x01` finger down, `0x08` "pulley" (finger held, nudged one step per wheel click).

## Modes
Hold ◀ + ▶ for 3 s to cycle modes (blue LED stays on 5 s). Use **pulley** mode:
it is the only one where every button is distinct. In the third mode the wheel
sends the same swipes as the arrows, so they can't be told apart.

## Pulley mode map
| Input | Report |
|-------|--------|
| Wheel click | digitizer frame, Y falling (forward) / rising (back), ~30 units per step |
| ◀ / ▶ | report `0x02`, bits `0x40` / `0x80` |
| Centre | Volume Down (`0xEA`) / Volume Up (`0xE9`), alternating |
| Centre ×2 | AC Home (`0x0223`), one event, no single-press events |
| Right ×2 | Next Track (`0xB5`) |
| Left ×2 | Previous Track (`0xB6`) |
| Bottom | touch down/up with no movement |

## macOS note
Open the device exclusively (seize it) or macOS also acts on the events
(volume changes, fake clicks). hidapi ≥ 0.12 does this by default.
