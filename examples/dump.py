"""Print every raw HID report from the ring. Useful for checking your unit.

    python examples/dump.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import hid
from jx11 import VENDOR_ID, PRODUCT_ID

for info in hid.enumerate(VENDOR_ID, PRODUCT_ID):
    print(f"found: usage_page={info.get('usage_page'):#x} product={info.get('product_string')!r}")

dev = hid.Device(vid=VENDOR_ID, pid=PRODUCT_ID)
print("listening, ctrl-c to stop")
while True:
    data = dev.read(64, timeout=500)
    if data:
        print(bytes(data).hex(" "))
