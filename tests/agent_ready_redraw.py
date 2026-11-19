"""Evidence for the pinned Codex prompt redraw; deliberately not a general VT decoder."""
import re

IDLE = b'\x1b]7501;state=idle:app=codex'
SGR = rb'(?:\x1b\[[0-9;:]*m)*'


def read_idle_redraw(wire, marker, read_screen):
    idle = wire.find(IDLE)
    if idle < 0:
        return None
    end = idle + len(IDLE)
    if wire.startswith(b'\x1b\\', end):
        start = end + 2
    elif wire.startswith(b'\x07', end):
        start = end + 1
    else:
        return None
    if not all(q in wire[:idle] for q in (b'\x1b]10;?', b'\x1b]11;?')):
        return None
    text = marker.encode('ascii')
    full = wire.find(text, start)
    if full >= 0:
        return dict(kind='complete-write', idle_offset=idle, write_offset=full)

    # Some frames repaint only the changed suffix. Require the unique complete
    # prompt in the actual viewport plus both matching writes at their cells.
    # A matching suffix elsewhere, a move without a write, and a marker left
    # unchanged since before idle cannot satisfy this witness.
    if len(wire) <= start:
        return None
    rows = read_screen().replace('\r','').split('\n')
    locations = [(i,line) for i,line in enumerate(rows,1) if marker in line]
    if len(locations) != 1:
        return None
    row, line = locations[0]
    if line.rstrip() != '› ' + marker:
        return None
    cup = b'\x1b[' + str(row).encode() + b';'
    prompt = re.escape(cup + b'1H') + SGR + re.escape('›'.encode()) + SGR + b' '
    for first in re.compile(prompt + rb'([A-Z0-9_]+)(?=\x1b)').finditer(wire, 0, idle):
        prefix = first.group(1)
        if len(prefix) >= len(text) or not text.startswith(prefix):
            continue
        col = 3 + len(prefix)  # '› ' occupies two cells in this fixture
        tail = re.escape(cup + str(col).encode() + b'H') + SGR + re.escape(text[len(prefix):]) + rb'(?=\x1b|$)'
        second = re.compile(tail).search(wire, start)
        if second:
            return dict(kind='split-redraw', idle_offset=idle, row=row, suffix_column=col,
                        prefix_write=first.start(1), suffix_write=second.start(),
                        prefix_length=len(prefix), suffix_length=len(text)-len(prefix))
    return None
