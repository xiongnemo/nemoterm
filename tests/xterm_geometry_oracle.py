"""Capture resize parameter semantics from pinned XTerm on a private Xvfb."""
import argparse
import json
from pathlib import Path
from xterm_state_oracle import run_cases

CSI = '\x1b['
query = ''.join(CSI+op+'t' for op in ('14', '14;2', '16', '18', '19'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', default='research/geometry-xterm.json')
    args = parser.parse_args()
    operations = {
        'baseline': '',
        'no-operation-default': 't',
        'no-operation-zero': '0t',
        'chars-explicit': '8;30;90t',
        'chars-omitted-both': '8t',
        'chars-empty-both': '8;;t',
        'chars-rows-only': '8;30t',
        'chars-empty-column': '8;30;t',
        'chars-empty-row': '8;;90t',
        'chars-zero-row': '8;0;90t',
        'chars-zero-column': '8;30;0t',
        'chars-zero-both': '8;0;0t',
        'chars-extra-parameters': '8;30;90;123t',
        'chars-subparameters': '8;30:1;90t',
        'pixels-exact-client': '4;210;482t',
        'pixels-not-cell-multiple': '4;217;489t',
        'pixels-omitted-both': '4t',
        'pixels-empty-both': '4;;t',
        'pixels-rows-only': '4;210t',
        'pixels-empty-column': '4;210;t',
        'pixels-empty-row': '4;;482t',
        'pixels-zero-row': '4;0;482t',
        'pixels-zero-column': '4;210;0t',
        'pixels-zero-both': '4;0;0t',
        'pixels-extra-parameters': '4;210;482;123t',
        'pixels-subparameters': '4;210:1;482t',
        'lines-24': '24t',
        'lines-31': '31t',
        'lines-48': '48t',
        'lines-extra-parameters': '31;99t',
        'lines-subparameters': '31:1t',
        'chars-too-large': '8;65536;90t',
        'pixels-too-large': '4;65536;482t',
        'chars-one-cell': '8;1;1t',
        'pixels-one': '4;1;1t',
        'pixels-small': '4;7;7t',
        'chars-omitted-after-pixels': '4;217;489t'+CSI+'8t',
        'pixels-omitted-after-pixels': '4;217;489t'+CSI+'4t',
        'pixels-saturated': '4;999999999999999999;482t',
    }
    # Each case begins with a different-than-default grid. This distinguishes
    # omitted/current dimensions from resource defaults and explicit zero.
    reset = CSI+'8;27;83t'
    cases = {name:reset+(CSI+op if op else '')+query for name,op in operations.items()}
    run_cases(args.xterm, args.output, cases, (
        '-fn', 'fixed', '-xrm', '*allowWindowOps: true',
        '-xrm', '*disallowedWindowOps:', '-xrm', '*limitResize: 1'), raw_replies=True)
    data = json.loads(Path(args.output).read_text())
    replies = data['cases']
    assert CSI+'8;27;83t' in replies['baseline']['reply'], replies['baseline']
    assert CSI+'8;30;90t' in replies['chars-explicit']['reply'], replies['chars-explicit']
    assert replies['chars-omitted-both']['reply'] == replies['baseline']['reply']
    assert CSI+'8;31;83t' in replies['lines-31']['reply'], replies['lines-31']
    print(f'Captured {len(cases)} independent geometry cases; baseline assertions passed')


if __name__ == '__main__':
    main()
