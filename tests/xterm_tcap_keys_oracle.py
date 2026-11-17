"""Observe startup termcap keyboards using an independently compiled database.

The XTerm setter has a separately retained upstream lifecycle discrepancy.
These captures select the database at startup, so successful database key
strings, modifier fallback and reset behavior can be observed independently.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

import xterm_udk_oracle as harness
from xterm_extended_keys_oracle import ObservedDisplay, prepare_keyboard
from xterm_locator_oracle import write
from xterm_udk_oracle import step

E = b'\x1b'
C = E + b'['
KEYS = ('F1', 'F5', 'F12', 'F20', 'F35', 'Up', 'Down', 'Left', 'Right',
        'Home', 'End', 'Insert', 'Delete', 'Prior', 'Next', 'KP_Enter',
        'KP_1', 'KP_Add', 'BackSpace', 'Tab')
REQUIRED = ('xterm-256color', 'linux', 'vt100', 'screen', 'tmux')
ADDITIONAL = ('vt220', 'ansi', 'rxvt-unicode-256color', 'alacritty',
              'xterm-kitty', 'wezterm', 'foot')
QUERY = E + b'P+q' + b';'.join(name.hex().encode() for name in (
    b'TN', b'Co', b'k1', b'k5', b'ku', b'kUP', b'kUP5', b'kh', b'kI', b'kD',
    b'kP', b'kent', b'kb', b'kB')) + E + b'\\'


def cases(available):
    result = {}
    translations = ['-xrm', 'XTerm*VT100.translations: #replace\\n<KeyPress>: insert-seven-bit()']

    def add(name, terminal, steps):
        result[name] = dict(profile='tcap', resources=translations + ['-tn', terminal],
                            selected_terminal=terminal, steps=steps)

    add('control-xterm-f1', 'xterm-256color', [step(key='F1', modifiers=())])
    add('control-linux-f1', 'linux', [step(key='F1', modifiers=())])
    add('control-linux-f5', 'linux', [step(key='F5', modifiers=())])
    for terminal in REQUIRED:
        add(terminal + '-queries', terminal, [step(QUERY)])
        for key in KEYS:
            add(terminal + '-key-' + key, terminal, [step(key=key, modifiers=tuple(
                name for bit, name in ((1, 'Shift_L'), (2, 'Alt_L'), (4, 'Control_L')) if mask & bit))
                for mask in range(8)])
        for resource, key in ((1, 'Up'), (2, 'F1'), (3, 'KP_Add')):
            add(terminal + '-resource-' + str(resource), terminal,
                [step(C + (f'>{resource}n' if level == -1 else f'>{resource};{level}m').encode(),
                      key=key, modifiers=modifiers)
                 for level in range(-1, 5)
                 for modifiers in ((), ('Shift_L',), ('Control_L',), ('Alt_L',))])
        for name, sequence, keys in (
                ('cursor-normal', C+b'?1l', ('Up', 'Home')),
                ('cursor-application', C+b'?1h', ('Up', 'Home')),
                ('keypad-normal', E+b'>', ('KP_1', 'KP_Enter')),
                ('keypad-application', E+b'=', ('KP_1', 'KP_Enter')),
                ('soft-reset', C+b'!p', ('Up', 'F1')),
                ('hard-reset', E+b'c', ('Up', 'F1')),
                ('alternate', C+b'?1049h'+C+b'?1049l', ('Up', 'F1'))):
            add(terminal + '-' + name, terminal,
                [step(sequence+QUERY)] + [step(key=key, modifiers=()) for key in keys])
    for terminal in ADDITIONAL:
        if terminal in available:
            add(terminal + '-startup', terminal,
                [step(QUERY)] + [step(key=key, modifiers=()) for key in KEYS])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--database-observations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        parser.error('Reference capture requires a GitHub-hosted runner')
    with gzip.open(args.database_observations, 'rt') as source:
        available = json.load(source)['terminals']
    if not set(REQUIRED) <= available.keys():
        raise RuntimeError('A required startup database is missing')
    folder = args.output.with_suffix('')
    folder.mkdir(parents=True, exist_ok=False)
    specs = cases(available)
    r, w = os.pipe()
    server = subprocess.Popen(['Xvfb', '-displayfd', str(w), '-screen', '0', '1024x768x24',
                               '-nolisten', 'tcp'], pass_fds=[w],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    display = ':' + os.read(r, 100).decode().strip()
    os.close(r)
    owner = ObservedDisplay(display)
    harness.Display = ObservedDisplay
    subprocess.run(['setxkbmap', '-display', display, '-option', '', '-option', 'srvrkeys:none'], check=True)
    result = dict(completed=False, executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                  database_observations_sha256=hashlib.sha256(args.database_observations.read_bytes()).hexdigest(),
                  unavailable=[name for name in ADDITIONAL if name not in available], cases={})
    controls = {'control-xterm-f1': b'\x1bOP', 'control-linux-f1': b'\x1b[[A',
                'control-linux-f5': b'\x1b[[E'}
    try:
        result['private_keyboard'] = prepare_keyboard(owner, set(KEYS) | {'Shift_L', 'Alt_L', 'Control_L'})
        for name, spec in specs.items():
            assert owner.x.XkbLockModifiers(owner.d, 256, 18, 0)
            owner.x.XSync(owner.d, False)
            observed = harness.capture_case(args.xterm, display, name, spec, folder)
            observed['selected_terminal'] = spec['selected_terminal']
            result['cases'][name] = observed
            write(args.output, result)
            if not observed['completed'] or observed['exit_code'] != 0:
                raise RuntimeError('Incomplete reference: ' + name)
            if name in controls:
                assert bytes.fromhex(observed['steps'][0]['reply_hex']) == controls[name], name
            print(name, len(observed['steps']), flush=True)
        result['completed'] = True
    finally:
        write(args.output, result)
        owner.close()
        server.terminate()
        server.wait(timeout=5)


if __name__ == '__main__':
    main()
