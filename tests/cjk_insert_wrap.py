"""A Chinese character inserted at the right edge must make room on its destination row."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from native_test_utils import root, u, w
from protocol_oracle_window import run

CSI = '\x1b['
SEED = '界V尾abcXYZ'


def row(text):
    # Count glyphs independently of the terminal. Keep CHAR_INFO's lead/trail
    # flags separate from the zero that the VT checksum reports for a trail.
    vt, native = [], []
    for ch in text:
        if ch in '中界尾':
            vt.extend([ord(ch), 0]); native.extend([[ord(ch), 0x100], [ord(ch), 0x200]])
        else:
            vt.append(ord(ch)); native.append([ord(ch), 0])
    return vt, native


def main(renderer):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    engine = {'gdi': 1, 'directx': 3}[renderer]
    label = 'column-cjk-insert-wrap-' + renderer
    results = {'product_sha256': hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest(), 'cases': {}}
    def observe(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        assert u.GetPropW(hwnd, 'NemotermRenderer') == engine
        for cluster in (False, True):
            for op in ('insert-wrapped', 'overwrite-wrapped', 'insert-direct', 'insert-pending-wrap'):
                name = op + ('-graphemes' if cluster else '-legacy')
                state = CSI + '?2027' + ('h' if cluster else 'l')
                setup = '\x1bc' + state + CSI + '9;1H' + SEED
                direct = op == 'insert-direct'
                # The ASCII x fills the last cell first in the pending-wrap control.
                start = CSI + ('9;1H' if direct else '8;80H')
                wire = setup + start + CSI + ('4l' if op == 'overwrite-wrapped' else '4h')
                wire += ('x' if op == 'insert-pending-wrap' else '') + '中' + CSI + '4l' + CSI + '31#y'
                expected = '中' + (SEED[1:] if op == 'overwrite-wrapped' else SEED)
                chars, native = row(expected)
                wire += ''.join(f'{CSI}{x};1;9;{x};9;{x}*y' for x in range(1, len(chars)+1))
                raw = phase(name, wire, None)
                matches = re.findall(rb'\x1bP(\d+)!~([0-9a-fA-F]{4})\x1b\\', raw)
                assert [int(k) for k,_ in matches] == list(range(1,len(chars)+1))
                assert b''.join(b'\x1bP'+k+b'!~'+v+b'\x1b\\' for k,v in matches) == raw
                actual = [int(v,16) for _,v in matches]
                snapshot = current(); assert snapshot['phase'] == name
                got = [[v,attr & 0x300] for v,attr in snapshot['native_row'][:len(chars)]]
                results['cases'][name] = dict(expected=expected, input_hex=wire.encode().hex(), reply_hex=raw.hex(),
                    expected_vt=chars, vt=actual, expected_native=native, native=got,
                    vt_ok=actual == chars, native_ok=got == native)
        return {'count': len(results['cases'])}
    try:
        run(label, [], exercise=observe, barrier=(CSI+'5n', b'\x1b[0n'), native_row=(0,8,16),
            source_reference='preserve existing destination text when inserting', font=os.environ['NEMOTERM_TEST_FONT'],
            profile=dict(NemoRenderer=engine-1,NemoAllowChecksum=1,UTF8linedraw=1,WarnOnClose=0))
        assert len(results['cases']) == 8
        failures = [(k,r['vt_ok'],r['native_ok']) for k,r in results['cases'].items() if not r['vt_ok'] or not r['native_ok']]
        assert not failures, failures
    finally:
        (root/'research'/(label+'-result.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
