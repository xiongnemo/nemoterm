"""Feed captured XTerm input directly into a new Linux PTY, with no frontend."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import termios
import time
import traceback
import tty
from zipfile import ZipFile


def sample(payload, marker, canonical):
    master, slave = os.openpty()
    result = {'slave': os.ttyname(slave), 'written_hex': payload.hex(), 'chunks': []}
    try:
        tty.setraw(slave)
        settings = termios.tcgetattr(slave)
        settings[6][termios.VLNEXT] = bytes([marker])
        if canonical:
            settings[3] |= termios.ICANON | termios.IEXTEN
            settings[0] |= termios.ICRNL
        termios.tcsetattr(slave, termios.TCSANOW, settings)
        actual = termios.tcgetattr(slave)
        result.update(iflag=actual[0], lflag=actual[3], lnext=actual[6][termios.VLNEXT][0])
        assert result['lnext'] == marker and bool(actual[3] & termios.ICANON) == canonical
        assert os.write(master, payload) == len(payload)
        received = bytearray()
        deadline = time.monotonic() + 5
        while len(received) < 4096:
            timeout = max(0, deadline - time.monotonic())
            if not select.select([slave], [], [], timeout)[0]:
                raise TimeoutError('did not receive the final record')
            piece = os.read(slave, 4096)
            if not piece:
                raise EOFError('PTY unexpectedly closed')
            result['chunks'].append(piece.hex())
            received.extend(piece)
            if (canonical and piece == b'7\n') or (not canonical and received.endswith(b'\r7')):
                break
        assert len(received) < 4096
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        os.close(master)
        os.close(slave)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    if os.environ.get('NEMO_HOSTED_PTY_FIXTURE') != '1' or platform.system() != 'Linux':
        raise RuntimeError('Requires the explicitly enabled hosted Linux fixture')
    digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    assert digest == '3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
    results = dict(kernel=platform.release(), version=Path('/proc/version').read_text(), reference_sha256=digest,
                   fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cases={})
    with ZipFile(args.archive) as z:
        for profile in ('default', 'custom'):
            ref = json.loads(z.read('paste-quote/' + profile + '.json'))
            marker = ref['tty_lnext']; text = bytes.fromhex(ref['clipboard_hex'])
            assert ref['completed'] and marker in (22, 29)
            for case, canonical in [('raw-reference', False), ('canonical-reference', True), ('canonical-scalar', True), ('canonical-unquoted', True)]:
                wire = bytes.fromhex(ref['cases']['restore-lf']['paste_hex'])  # 2005 and 2006, no framing
                assert wire[1::2] == text and wire[::2] == bytes([marker])*len(text)
                if case == 'canonical-scalar':
                    wire = b''.join(bytes([marker]) + c.encode() for c in text.decode())
                if case == 'canonical-unquoted':
                    wire = text
                payload = wire + (b'\r7\r' if canonical else b'\r7')
                row = sample(payload, marker, canonical)
                expected = ([r + b'\n' for r in text.split(b'\n')] + [b'7\n'] if case == 'canonical-unquoted'
                            else [text + b'\n', b'7\n'] if canonical else [payload])
                row['expected_chunks'] = [p.hex() for p in expected]
                row['matches'] = ('error' not in row and (row['chunks'] == row['expected_chunks'] if canonical else
                                  ''.join(row['chunks']) == payload.hex()))
                results['cases'][profile + '/' + case] = row
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    assert all(r['matches'] for r in results['cases'].values()), 'See the raw and canonical slave reads'


if __name__ == '__main__':
    main()
