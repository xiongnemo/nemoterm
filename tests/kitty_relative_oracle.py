"""Observe relative placements in pinned, unmodified, compiled upstream kitty.

This executes the upstream parser and graphics manager under REA. It records
wire replies, image identity, raw layers and cursor state; it does not calculate
expected parent positions or run Nemoterm.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import unittest

UPSTREAM = '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
COLS, ROWS, CW, CH = 12, 8, 10, 20


def command(header, payload=None):
    return (b'\x1b_G' + header.encode('ascii') +
            (b';' + base64.b64encode(payload) if payload is not None else b'') + b'\x1b\\')


def picture(image=1, **fields):
    keys = dict(a='T', f=24, i=image, s=2, v=2, C=1)
    keys.update(fields)
    return command(','.join(f'{k}={v}' for k, v in keys.items()),
                   bytes({1: (255, 0, 0), 2: (0, 255, 0)}.get(image, (0, 0, 255))) * 4)


def make_cases():
    seed = b'\x1b[3;4H' + picture(p=11, c=2, r=2, X=3, Y=5)
    load = picture(2, a='t')
    child = command('a=p,i=2,p=22,P=1,Q=11,H=1,V=1')
    cases = []

    def add(name, steps, initial=None):
        cases.append((name, [('seed', seed + load if initial is None else initial), *steps]))

    for name, extra in [
        ('coincident', ''), ('positive-offset', ',H=2,V=1'),
        ('negative-offset', ',H=-1,V=-1'), ('child-pixel-offset', ',X=4,Y=6'),
        ('explicit-grid', ',c=2,r=3'), ('crop', ',x=1,y=1,w=1,h=1,c=2,r=1'),
        ('cursor-zero', ',C=0'), ('cursor-one', ',C=1'),
        ('parent-first-placement', ',Q=0'), ('quiet-success', ',q=1'),
        ('quiet-all', ',q=2'), ('negative-z', ',z=-1'),
    ]:
        add(name, [('child', command('a=p,i=2,p=22,P=1,Q=11' + extra))])

    for name, header in [
        ('missing-parent-image', 'a=p,i=2,p=22,P=99,Q=11'),
        ('missing-parent-placement', 'a=p,i=2,p=22,P=1,Q=99'),
        ('self-parent', 'a=p,i=1,p=11,P=1,Q=11'),
        ('virtual-relative-rejected', 'a=p,i=2,p=22,U=1,P=1,Q=11'),
        ('missing-child-image', 'a=p,i=99,p=22,P=1,Q=11'),
        ('quiet-missing-parent', 'a=p,i=2,p=22,P=99,q=1'),
        ('silent-missing-parent', 'a=p,i=2,p=22,P=99,q=2'),
        ('ignored-Q-without-P', 'a=p,i=2,p=22,Q=99,C=1'),
        ('ignored-HV-without-P', 'a=p,i=2,p=22,H=2,V=-1,C=1'),
        ('same-image-child', 'a=p,i=1,p=22,P=1,Q=11,H=2,V=1'),
    ]:
        add(name, [('request', command(header)),
                   ('parent-remains', b'\x1b[5;7H' + command('a=p,i=1,p=11,C=1'))])
    add('parent-has-no-placement', [
        ('load-parent', picture(3, a='t')),
        ('child', command('a=p,i=2,p=22,P=3'))])

    add('parent-movement', [('child', child),
        ('move-parent', b'\x1b[5;7H' + command('a=p,i=1,p=11,C=1')),
        ('parent-pixel-offset', command('a=p,i=1,p=11,C=1,X=8,Y=14')),
        ('parent-new-z', command('a=p,i=1,p=11,C=1,z=10'))])
    add('child-replacement', [('child', child),
        ('move-child', command('a=p,i=2,p=22,P=1,Q=11,H=-1,V=2')),
        ('detach-child', b'\x1b[2;2H' + command('a=p,i=2,p=22,C=1')),
        ('move-former-parent', b'\x1b[5;7H' + command('a=p,i=1,p=11,C=1'))])
    add('first-parent-is-creation-order', [
        ('second-parent', b'\x1b[6;9H' + command('a=p,i=1,p=44,z=-10,C=1')),
        ('child-implicit-parent', command('a=p,i=2,p=22,P=1')),
        ('move-first-parent', b'\x1b[1;2H' + command('a=p,i=1,p=11,C=1')),
        ('remove-first-parent', command('a=d,d=i,i=1,p=11')),
        ('child-data-after-cascade', command('a=p,i=2,p=22,C=1'))])
    add('anonymous-first-parent', [('child', command('a=p,i=2,p=22,P=1,H=2')),
        ('delete-parent-image', command('a=d,d=i,i=1'))],
        initial=b'\x1b[3;4H' + picture() + load)

    grandchild = command('a=p,i=2,p=23,P=2,Q=22,H=1,V=1')
    for name, loop in [('cycle-two', 'a=p,i=1,p=11,P=2,Q=22'),
                       ('cycle-three', 'a=p,i=1,p=11,P=2,Q=23')]:
        add(name, [('child', child), ('grandchild', grandchild),
                   ('reject-cycle', command(loop)),
                   ('move-root-after-rejection', b'\x1b[2;3H' + command('a=p,i=1,p=11,C=1'))])
    chain = [('child-depth-1', child)]
    for depth in range(2, 10):
        chain.append((f'child-depth-{depth}', command(f'a=p,i=2,p={21+depth},P=2,Q={20+depth}')))
    chain += [('root-after-depth-error', b'\x1b[4;6H' + command('a=p,i=1,p=11,C=1')),
              ('replace-with-too-deep-parent', command('a=p,i=1,p=11,P=2,Q=29')),
              ('remove-root', command('a=d,d=i,i=1,p=11')),
              ('child-data-after-cascade', command('a=p,i=2,p=22,C=1'))]
    add('bounded-ancestry', chain)

    for name, deletion in [
        ('parent-placement', 'a=d,d=i,i=1,p=11'), ('parent-image-data', 'a=d,d=I,i=1'),
        ('parent-image-views', 'a=d,d=i,i=1'), ('visible-views', 'a=d,d=a'),
        ('visible-data', 'a=d,d=A'), ('parent-range', 'a=d,d=r,x=1,y=1'),
        ('parent-range-data', 'a=d,d=R,x=1,y=1'), ('parent-column', 'a=d,d=x,x=4'),
        ('parent-row', 'a=d,d=y,y=3'), ('parent-point', 'a=d,d=p,x=4,y=3'),
        ('parent-z-point', 'a=d,d=q,x=4,y=3,z=0'),
        ('parent-cursor', 'a=d,d=c'), ('child-only', 'a=d,d=i,i=2,p=22'),
    ]:
        add('delete-' + name, [('child', child), ('grandchild', grandchild),
            ('delete', command(deletion)), ('try-child-data', command('a=p,i=2,p=88,C=1'))])
    add('child-image-has-independent-placement', [('child', child),
        ('independent-child-view', b'\x1b[7;8H' + command('a=p,i=2,p=88,C=1')),
        ('delete-parent', command('a=d,d=i,i=1,p=11')),
        ('child-data-kept', command('a=p,i=2,p=99,C=1'))])
    add('replace-parent-data', [('child', child), ('grandchild', grandchild),
        ('replace-parent', picture(p=11)), ('try-child-data', command('a=p,i=2,p=88,C=1'))])
    add('recreate-parent-id', [('child', child),
        ('delete-root', command('a=d,d=I,i=1')),
        ('recreate-root', picture(p=11)), ('old-child-not-reattached', command('a=p,i=2,p=22,C=1'))])
    add('missing-reparent-is-atomic', [('child', child),
        ('invalid-parent', command('a=p,i=2,p=22,P=99')),
        ('move-original-parent', b'\x1b[5;6H' + command('a=p,i=1,p=11,C=1'))])

    for name, wire in [
        ('page-scroll', b'\x1b[8;1H\n'), ('reverse-scroll', b'\x1b[H\x1bM'),
        ('margin-scroll', b'\x1b[2;5r\x1b[5;1H\n'),
        ('margin-clip-parent', b'\x1b[2;5r\x1b[5;1H\n\n\n'),
        ('clear-display', b'\x1b[2J'), ('clear-history', b'\x1b[3J'),
        ('reset', b'\x1bc'), ('alternate-screen', b'\x1b[?1049h\x1b[?1049l'),
        ('text-overwrite', b'abc'), ('insert-delete-lines', b'\x1b[L\x1b[M'),
    ]:
        add(name, [('child', child), ('grandchild', grandchild), (name, wire)])
    add('parent-in-history-child-visible', [
        ('child-below', command('a=p,i=2,p=22,P=1,Q=11,V=3')),
        ('parent-above-screen', b'\x1b[8;1H\n\n\n\n'),
        ('parent-outside-history', b'\x1b[8;1H' + b'\n' * 25),
        ('child-data-after-history', command('a=p,i=2,p=88,C=1'))])
    add('child-offscreen-returns', [
        ('offscreen-child', command('a=p,i=2,p=22,P=1,Q=11,H=-4')),
        ('parent-makes-child-visible', b'\x1b[4;8H' + command('a=p,i=1,p=11,C=1'))])
    add('virtual-parent', [
        ('virtual-root', picture(42, U=1, c=2, r=2)),
        ('relative-child', command('a=p,i=2,p=22,P=42,H=1,V=1')),
        ('placeholder', b'\x1b[2;2H\x1b[38;5;42m' + '\U0010eeee\u0305\u0305'.encode() + b'\x1b[0m'),
        ('earlier-placeholder', b'\x1b[H\x1b[38;5;42m' + '\U0010eeee\u0305\u0305'.encode() + b'\x1b[0m'),
        ('erase-placeholders', b'\x1b[2J')])
    assert len({name for name, _ in cases}) == len(cases)
    return cases


def main():
    import kitty.fast_data_types as native
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.graphics import TestGraphics
    from kitty_tests.main import env_for_python_tests

    source = Path(os.environ['NEMOTERM_KITTY_REFERENCE_SOURCE']).resolve()
    output = Path(os.environ['NEMOTERM_KITTY_REFERENCE_OUTPUT']).resolve()
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == UPSTREAM
    inputs = make_cases()
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record = dict(status='running', family='kitty-relative', upstream_commit=commit,
        scope='Compiled upstream parent lifetime, layout and replies; no OS window/GPU pixels',
        observation_effects=['update_only_line_graphics_data', 'update_layers'],
        fixture_sha256=sha(__file__), platform=platform.platform(), python=platform.python_version(),
        source_sha256={p:sha(source/p) for p in ('kitty/graphics.c', 'kitty_tests/graphics.py', 'docs/graphics-protocol.rst')},
        compiled_sha256={p:sha(source/p) for p in ('kitty/launcher/kitty', str(Path(native.__file__).relative_to(source)))},
        geometry=dict(columns=COLS, rows=ROWS, cell_width=CW, cell_height=CH),
        expected_cases=[name for name, _ in inputs], cases=[])

    def save():
        output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')

    save()
    with env_for_python_tests():
        names = ['test_image_parents', 'test_image_put', 'test_gr_scroll']
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(TestGraphics(n) for n in names))
        record['upstream_tests'] = dict(names=names, run=result.testsRun, failures=len(result.failures),
            errors=len(result.errors), skipped=len(result.skipped), successful=result.wasSuccessful())
        save()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError('Upstream parent/layout/scroll controls did not all pass')
        for name, steps in inputs:
            helper = BaseTest()
            screen = helper.create_screen(COLS, ROWS, scrollback=20, cell_width=CW, cell_height=CH)
            case = dict(name=name, steps=[])
            record['cases'].append(case)
            try:
                for label, wire in steps:
                    screen.callbacks.clear()
                    parse_bytes(screen, wire)
                    before_layers = screen.grman.image_count
                    screen.update_only_line_graphics_data()
                    layers = screen.grman.update_layers(screen.scrolled_by, -1, 1,
                        2/COLS, 2/ROWS, COLS, ROWS, CW, CH)
                    # Do not call image_for_client_id to probe missing images:
                    # upstream's test convenience lookup creates them on miss.
                    case['steps'].append(dict(label=label, input_base64=base64.b64encode(wire).decode('ascii'),
                        reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode('ascii'),
                        cursor=[screen.cursor.x, screen.cursor.y], image_count=screen.grman.image_count,
                        image_count_before_layers=before_layers,
                        scrolled_by=screen.scrolled_by, layers=layers))
                    save()
                print('Captured relative placement:', name, len(steps), 'states', flush=True)
            finally:
                screen.reset()
                helper.tearDown()
    record.update(status='complete', case_count=len(record['cases']),
                  state_count=sum(len(c['steps']) for c in record['cases']))
    save()
    print('Completed relative-placement reference:', record['case_count'], record['state_count'], flush=True)


if __name__ == '__main__':
    main()
