"""Print high-level ring events.

    python examples/events.py
"""
import sys, os, time, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from jx11 import Ring

logging.basicConfig(level=logging.INFO)
ring = Ring()
ring.on("scroll", lambda s: print("scroll", s))
for name in ("centre", "centre_double", "bottom", "left", "right", "left_double", "right_double"):
    ring.on(name, lambda n=name: print(n))
ring.start()
while True:
    time.sleep(1)
