"""Capture modifier negotiation and real key events on a private Xvfb server.

The unmodified, pinned XTerm supplies every expected byte. This fixture never
opens the Windows desktop and does not access either platform's clipboard.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from xterm_locator_oracle import Display, write
from xterm_udk_oracle import capture_case, prepare_keyboard, step

C = b'\x1b['


def cases():
    result = {}
    modifiers = [tuple(m for bit, m in ((1, 'Shift_L'), (2, 'Alt_L'), (4, 'Control_L'))
                       if mask & bit) for mask in range(8)]

    def add(name, sequence, key, masks=range(8)):
        result[name] = dict(profile='default', steps=[
            dict(**step(sequence, key, modifiers[mask]), key=key, modifiers=mask)
            for mask in masks])

    add('control-up', b'', 'Up', (0,))
    add('control-function', b'', 'F1', (0, 6))
    add('control-editing', b'', 'Insert', (1,))

    def setting(resource, level):
        return C+(f'>{resource}n' if level == 'disabled' else f'>{resource};{level}m').encode()

    for level in ('disabled', 0, 1, 2, 3, 4):
        for fmt in ((0, 1) if level == 4 else (0,)):
            for key, resource, app in (('Up', 1, False), ('Up', 1, True),
                                       ('F1', 2, False), ('F5', 2, False)):
                sequence = setting(resource, level)+C+f'>{resource};{fmt}f'.encode()
                sequence += C+(b'?1h' if app else b'?1l')+C+f'?{resource}m'.encode()
                add(f'{key}-app{int(app)}-level{level}-format{fmt}', sequence, key)
    for key in ('Left', 'Right', 'Down', 'Home', 'End', 'Prior', 'Next', 'Insert', 'Delete', 'F12', 'F20'):
        for level in ('disabled', 3, 4):
            # Set both resources so this also observes XTerm's editing-key classification.
            sequence = setting(1, level)+setting(2, level)
            add(f'editing-{key}-level{level}', sequence, key, (0, 1, 4, 6))
    query = C+b'?1;2;4m'+C+b'>1;2;4g'
    initial = C+b'>1;3:5m'+C+b'>2;1:7m'+C+b'>1;1f'+C+b'>2;1f'
    for name, sequence in {
        'initial': b'', 'reset-all': C+b'>m'+C+b'>f',
        'reset-one': C+b'>1m'+C+b'>2f', 'disable-default': C+b'>n',
        'disable-cursor': C+b'>1n', 'disable-function': C+b'>2n',
        'ris': b'\x1bc', 'soft-reset': C+b'!p',
        'dec-level': C+b'63;1"p', 'alternate': C+b'?1049h'+C+b'?1049l',
        'cursor-save': b'\x1b7'+C+b'>1;2m'+b'\x1b8',
    }.items():
        result['state-'+name] = dict(profile='default', steps=[
            dict(**step(initial+sequence+query), key=None, modifiers=0)])
    for resource in (1, 2):
        for level in (0, 3, 4):
            add(f'mask-resource{resource}-level{level}',
                C+f'>{resource};{level}:5m'.encode()+b'\x1bP$q'+f'>{resource}m'.encode()+b'\x1b\\',
                'Up' if resource == 1 else 'F1', (1, 4, 5, 7))
    for spec in result.values():
        # Keep this protocol reference independent of XTerm's default local
        # Shift+Insert paste and Shift+PageUp scroll bindings.
        spec['resources'] = ['-xrm', 'XTerm*VT100.translations: #replace\\n<KeyPress>: insert-seven-bit()']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    folder = output.with_suffix('')
    folder.mkdir(exist_ok=False)
    r, w = os.pipe()
    xvfb = subprocess.Popen(['Xvfb', '-displayfd', str(w), '-screen', '0', '1024x768x24',
                             '-nolisten', 'tcp'], pass_fds=[w], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    os.close(w)
    display = ':'+os.read(r, 100).decode().strip()
    os.close(r)
    owner = Display(display)
    # Xorg otherwise consumes Ctrl+Alt+Fn as a virtual-console switch, even
    # on Xvfb. Change only this newly created private server's keyboard map.
    subprocess.run(['setxkbmap', '-display', display, '-option', '',
                    '-option', 'srvrkeys:none'], check=True)
    result = dict(completed=False, version=subprocess.check_output([args.xterm, '-version'], text=True).strip(),
                  executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                  fixtures={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [Path(__file__), Path(__file__).with_name('xterm_udk_oracle.py'),
                             Path(__file__).with_name('xterm_locator_oracle.py')]}, cases={})
    try:
        result['private_keyboard'] = prepare_keyboard(owner)
        controls = {'control-up': [b'\x1b[A'],
                    'control-function': [b'\x1bOP', b'\x1b[1;7P'],
                    'control-editing': [b'\x1b[2;2~']}
        for name, spec in cases().items():
            observed = capture_case(args.xterm, display, name, spec, folder)
            result['cases'][name] = observed
            write(output, result)
            assert observed['completed'] and observed['exit_code'] == 0
            if name in controls:
                assert [bytes.fromhex(s['reply_hex']) for s in observed['steps']] == controls[name], name
            print(name, len(observed['steps']), flush=True)
        result['completed'] = True
    finally:
        write(output, result)
        owner.close()
        xvfb.terminate()
        xvfb.wait(timeout=5)


if __name__ == '__main__':
    main()
