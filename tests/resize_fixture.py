"""Observe ConPTY sizes from inside a real child during the resize smoke test."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
report = Path(sys.argv[1])
observed = []
last = None
start = time.monotonic()
print('\x1b]2;Nemoterm resize verification\x07', end='')
while time.monotonic()-start < 45:
    size = os.get_terminal_size()
    if size != last:
        last = size
        observed.append({'columns':size.columns,'rows':size.lines})
        report.write_text(json.dumps(observed), encoding='utf-8')
        print(f'\x1b[HConPTY size: {size.columns}x{size.lines}\x1b[K')
        print('中文宽字符 A\u0301 combining | resize keeps application and terminal in sync')
        print('0123456789 '*min(size.columns//10, 10))
        sys.stdout.flush()
    time.sleep(0.1)
