"""Capture XTerm's actual named-colour replies, retaining any differences.

Prepared only: run under Linux/WSL after runtime testing resumes. Source-derived
expectations are compared only after the independent raw capture is saved.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from xterm_state_oracle import run_cases

ROOT = Path(__file__).resolve().parent.parent


def cases():
    spec = importlib.util.spec_from_file_location('x11_data', ROOT / 'scripts/generate-x11-colours.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [(name, rgb) for name, rgb in module.records()]
    rows += [(name.swapcase(), rgb) for name, rgb in module.records()]
    rows += [(name, (1, 2, 3)) for name in (
        'gray101', 'grey-1', 'RED5', 'gray 50', 'light  blue',
        'light\tblue', 'red ', ' red', 'light goldenrod yellow!', 'not-a-colour')]
    result, expected = {}, {}
    # Keep each batch below the terminal's OSC/pipe limits and the collector's
    # lifetime. Each name starts from a sentinel, so rejection is observable.
    for start in range(0, len(rows), 24):
        key = f'x11-names-{start:04d}'
        sequence, reply = '', ''
        for offset, (name, rgb) in enumerate(rows[start:start+24]):
            end = '\x07' if (start + offset) % 2 else '\x1b\\'
            sequence += f'\x1b]4;1;#010203{end}\x1b]4;1;{name};1;?{end}'
            reply += '\x1b]4;1;rgb:' + '/'.join(f'{c*257:04x}' for c in rgb) + end
        result[key], expected[key] = sequence, reply
    return result, expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/x11-colour-xterm.json')
    args = parser.parse_args()
    sequences, expected = cases()
    run_cases(args.xterm, args.output, sequences, ['-ti', 'vt520'], raw_replies=True)
    captured = json.loads(Path(args.output).read_text(encoding='utf-8'))['cases']
    differences = [name for name, sequence in sequences.items()
                   if captured[name]['sequence'] != sequence or
                   captured[name]['reply_hex'] != expected[name].encode().hex()]
    if differences:
        raise SystemExit('XTerm differs from the pinned Xorg table: ' + ', '.join(differences))
    print(f'{len(sequences)} captured batches match the source-derived expectations')
