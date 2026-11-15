"""Capture OSC 22 through the pinned upstream parser and Window callback.

Run only in the disposable Linux reference workflow under REA. This fixture
authors input bytes, not the expected shape stack or query responses. It does
not create an OS window or establish platform cursor pixels.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from types import SimpleNamespace

UPSTREAM = '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
SHAPES = ('alias cell copy crosshair default e-resize ew-resize grab grabbing '
          'help move n-resize ne-resize nesw-resize no-drop not-allowed ns-resize '
          'nw-resize nwse-resize pointer progress s-resize se-resize sw-resize '
          'text vertical-text w-resize wait zoom-in zoom-out').split()
ALIASES = ('arrow left_ptr xterm ibeam beam hand hand1 hand2 pointing_hand '
           'question_arrow whats_this clock watch half-busy left_ptr_watch '
           'tcross plus cross fleur pointer-move right_side top_right_corner '
           'top_left_corner top_side bottom_right_corner bottom_left_corner '
           'bottom_side left_side sb_h_double_arrow sb_v_double_arrow '
           'size_bdiag size_fdiag dnd-link link dnd-copy forbidden crossed_circle '
           'dnd-no-drop openhand closedhand dnd-none').split()


def osc(value, end=b'\x1b\\'):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return b'\x1b]22;' + value + end


def make_cases():
    current = osc('?__current__')
    cases = []

    def add(name, *steps):
        cases.append((name, [(f'step-{i}', wire) for i, wire in enumerate(steps)]))

    add('default-queries', osc('?__current__,__default__,__grabbed__'),
        osc('?' + ','.join(SHAPES)), osc('?' + ','.join(ALIASES)))
    for name in SHAPES + ALIASES:
        add('shape-' + name, osc(name) + current, osc('?'+name),
            osc('>wait') + current, osc('<') + current)
    for value in ('', '=', '>', '<', '<ignored,names', 'bogus', '=bogus', '>bogus',
                  'text,pointer', '=text,pointer', '>text,pointer', 'text,,pointer',
                  ',text,', '>,text,,pointer,', '?', '?,', '?text,,bogus',
                  '?__current__,__current__,__default__,__grabbed__',
                  ' Pointer', 'POINTER', 'pointer ', 'pointer;wait', 'pointer\t',
                  'pointer\u00e9', 'none'):
        add('syntax-' + str(len(cases)), osc('text'), osc(value) + current,
            osc('<') + current)
    for length in (15, 16, 17, 18, 20, 33):
        values = [SHAPES[i % len(SHAPES)] for i in range(length)]
        steps = [osc('>'+','.join(values)) + current]
        steps.extend(osc('<') + current for _ in range(length+2))
        add(f'stack-capacity-{length}', *steps)
    for mode in (47, 1047, 1049):
        enter = f'\x1b[?{mode}h'.encode()
        leave = f'\x1b[?{mode}l'.encode()
        add(f'screen-{mode}', osc('>text,pointer') + current,
            enter + current, osc('>crosshair,wait') + current,
            leave + current, enter + current, osc('<') + current,
            leave + current, osc('<') + current)
    for reset in (b'\x1bc', b'\x1b[!p'):
        add('reset-' + reset.hex(), osc('>text,pointer'),
            b'\x1b[?1049h' + osc('>crosshair,wait') + current,
            reset + current, b'\x1b[?1049l' + current,
            b'\x1b[?1049h' + current)
    add('mouse-modes', osc('pointer') + current,
        b'\x1b[?1000h' + current, b'\x1b[?1000l' + current,
        b'\x1b[?1003;1006h' + current, b'\x1b[?1003;1006l' + current)
    add('erase-save-restore', osc('pointer') + b'\x1b7' + osc('wait') + current,
        b'\x1b8' + current, b'\x1b[2J' + current, b'\x1b[3J' + current)
    add('bel-terminator', osc('pointer', b'\x07'), osc('?__current__', b'\x07'))
    for cancel in (b'\x18', b'\x1a', b'\x1b[0m'):
        add('cancel-' + cancel.hex(), osc('text'),
            b'\x1b]22;pointer' + cancel + current)
    add('embedded-nul', osc('text'), osc(b'pointer\0wait') + current)
    add('long-unknown', osc('text'), osc('x'*2048) + current)
    cases.append(('bytewise', [('all-bytewise', osc('>text,pointer,wait') + current +
                               osc('<') + current + osc('?pointer,bogus,__current__'))]))
    return cases


def main():
    import kitty.fast_data_types as native
    from kitty.window import Window
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.main import env_for_python_tests

    source = Path(os.environ['NEMOTERM_KITTY_REFERENCE_SOURCE']).resolve()
    output = Path(os.environ['NEMOTERM_KITTY_REFERENCE_OUTPUT']).resolve()
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == UPSTREAM
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    cases = make_cases()
    record = dict(status='running', family='kitty-pointer', upstream_commit=commit,
        scope='Unmodified upstream parser, Python Window OSC 22 callback and native shape stack; no OS cursor or GPU pixels',
        fixture_sha256=sha(__file__), platform=platform.platform(), python=platform.python_version(),
        source_sha256={p:sha(source/p) for p in ('kitty/screen.c', 'kitty/window.py',
            'kitty/vt-parser.c', 'kitty_tests/base.py', 'docs/pointer-shapes.rst')},
        compiled_sha256={p:sha(source/p) for p in ('kitty/launcher/kitty', str(Path(native.__file__).relative_to(source)))},
        expected_cases=[name for name, _ in cases], controls=[], cases=[])

    def save():
        output.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    def create():
        helper = BaseTest()
        screen = helper.create_screen(cols=20, lines=8)
        window = SimpleNamespace(screen=screen)
        # Use the real upstream window dispatcher, including its response
        # framing. The native test callback otherwise discards OSC 22.
        screen.callbacks.set_pointer_shape = lambda data: Window.set_dynamic_color(window, 22, data)
        return helper, screen

    save()
    with env_for_python_tests():
        helper, screen = create()
        try:
            for label, wire, expected in (
                ('empty-stack-query', osc('?__current__'), osc('0')),
                ('literal-set-query', osc('pointer')+osc('?__current__'), osc('pointer')),
                ('literal-support-query', osc('?pointer,no-such-shape,wait'), osc('1,0,1'))):
                screen.callbacks.clear()
                parse_bytes(screen, wire)
                reply = bytes(screen.callbacks.wtcbuf)
                assert reply == expected, (label, reply, expected)
                record['controls'].append(dict(name=label, passed=True,
                    input_base64=base64.b64encode(wire).decode(),
                    reply_base64=base64.b64encode(reply).decode()))
            save()
        finally:
            screen.reset()
            helper.tearDown()
        for name, steps in cases:
            helper, screen = create()
            case = dict(name=name, steps=[])
            record['cases'].append(case)
            try:
                for label, wire in steps:
                    screen.callbacks.clear()
                    chunks = [wire[i:i+1] for i in range(len(wire))] if label.endswith('-bytewise') else [wire]
                    for chunk in chunks:
                        parse_bytes(screen, chunk)
                    case['steps'].append(dict(label=label, input_base64=base64.b64encode(wire).decode(),
                        chunk_bytes=[len(c) for c in chunks],
                        reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode(),
                        current_shape=screen.current_pointer_shape(),
                        cursor=[screen.cursor.x,screen.cursor.y],
                        rows=[str(screen.line(i)) for i in range(8)]))
                    save()
            finally:
                screen.reset()
                helper.tearDown()
            print('Captured pointer case:', name, len(steps), flush=True)
    record.update(status='complete', case_count=len(cases),
                  state_count=sum(len(case['steps']) for case in record['cases']))
    save()
    print('Completed pointer reference:', record['case_count'], record['state_count'], flush=True)


if __name__ == '__main__':
    main()
