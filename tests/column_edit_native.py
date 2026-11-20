"""Read the edited row via both VT and the console API on a hosted Windows runner."""
import hashlib
import json
import os
from pathlib import Path

from column_press_cells import CSI, ESC, cells
from native_test_utils import root, u, w
from protocol_oracle_window import run

# Each row spans 26 cells; columns 5..22 are inside the scrolling rectangle.
SHAPES = {
    'ascii': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'room': 'ABCDEFGHIJKLMNOPQR中UVWXYZ',
    'one-left': 'ABCDEFGHIJKLMNOPQRS中VWXYZ',
    'flush': 'ABCDEFGHIJKLMNOPQRST中WXYZ',
    'adjacent': 'ABCDEFGHIJKLMNOPQR中界WXYZ',
    'split-right': 'ABCDEFGHIJKLMNOPQRSTU中XYZ',
    'split-cursor': 'ABCD中GHIJKLMNOPQRSTUVWXYZ',
    'split-left': 'ABC中FGHIJKLMNOPQRSTUVWXYZ',
}
OPERATIONS = {'before': (0, ''), 'ich': (1, '@'), 'dch': (-1, 'P'),
              'decic': (1, "'}"), 'decdc': (-1, "'~"), 'sr': (1, ' A'), 'sl': (-1, ' @')}
QUERY = CSI+'?69l'+CSI+'31#y'+''.join(f'{CSI}{x};1;9;{x};9;{x}*y' for x in range(1, 27))


def expected(line, left, shift):
    # Move only complete source glyphs that fit inside the right margin.
    # Windows CHAR_INFO repeats the UCS-2 glyph, distinguishing halves by flags;
    # VT's checksum instead encodes the continuation as zero.
    vt, native = [32]*26, [[32, 0] for _ in range(26)]
    x = 0
    for glyph in line:
        wide = glyph in '中界'
        end = x + (2 if wide else 1)
        if shift == 0 or end <= left or x >= 22:
            dest = x
        elif left <= x and end <= 22 and left <= x + shift and end + shift <= 22:
            dest = x + shift
        else:
            dest = None
        if dest is not None:
            v = ord(glyph)
            vt[dest], native[dest] = v, [v, 0x100 if wide else 0]
            if wide:
                vt[dest+1], native[dest+1] = 0, [v, 0x200]
        x = end
    assert x == len(vt) == len(native) == 26
    return vt, native


def scenarios():
    for shape, line in SHAPES.items():
        for op, (direction, final) in OPERATIONS.items():
            for count in ((0,) if op == 'before' else (1, 2)):
                yield f'{shape}-{op}-{count}', line, '9;6', op, count, direction*count
    # ICH/DCH affect only the cursor row; the four other edits affect the pane.
    for op, (direction, final) in OPERATIONS.items():
        if op != 'before':
            yield 'other-row-'+op, SHAPES['room'], '10;6', op, 1, 0 if op in ('ich','dch') else direction
    for op in ('sr', 'sl'):
        for pos in ('9;4', '9;23', '4;6', '18;6'):
            yield 'outside-'+pos+'-'+op, SHAPES['room'], pos, op, 1, 0
        # Larger than the region: erase exactly the pane, including split glyphs.
        yield 'saturate-'+op, SHAPES['split-right'], '9;6', op, 99, OPERATIONS[op][0]*18


def main(renderer):
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('GitHub-hosted Windows required')
    name = 'column-edit-native-'+renderer
    engine = {'gdi': 1, 'directx': 3}[renderer]
    result = dict(executable_sha256=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest(), cases={})
    rows = result['cases']

    def observe(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        result['renderer'] = u.GetPropW(hwnd, 'NemotermRenderer')
        assert result['renderer'] == engine
        for key, line, pos, op, count, shift in scenarios():
            command = (ESC+'c'+CSI+'9;1H'+line+CSI+'?69h'+CSI+'5;22s'+CSI+'5;17r'+CSI+pos+'H'
                       + (CSI+str(count)+OPERATIONS[op][1] if count else '') + QUERY)
            vt, native = expected(line, 4 if op in ('sr','sl') else 5, shift)
            row = rows[key] = dict(input_hex=command.encode().hex(), expected_vt=vt, expected_native=native)
            raw = phase(key, command, None)
            state = current()
            assert state['phase'] == key and len(state['native_row']) == 26
            row.update(reply_hex=raw.hex(), vt=cells(raw), native=state['native_row'])
            public = [[unit, flags & 0x300] for unit,flags in row['native']]
            row['vt_differences'] = [x+1 for x in range(26) if row['vt'][x] != vt[x]]
            row['native_differences'] = [x+1 for x in range(26) if public[x] != native[x]]
        return {'cases': len(rows)}

    try:
        run(name, [], exercise=observe, barrier=(CSI+'5n', b'\x1b[0n'), native_row=(0, 8, 26),
            font=os.environ['NEMOTERM_TEST_FONT'], source_reference='complete source glyphs and native CHAR_INFO',
            profile=dict(NemoTabs=1, NemoRenderer=engine-1, NemoAllowChecksum=1, UTF8linedraw=1, FontHeight=8, WarnOnClose=0))
        assert len(rows) == 120
        failures = [k for k,r in rows.items() if r['vt_differences'] or r['native_differences']]
        assert not failures, failures
    finally:
        (root/'research'/(name+'-result.json')).write_text(json.dumps(result, separators=(',',':')), encoding='utf8')


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
