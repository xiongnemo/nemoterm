"""Observe feature-query replies and state in pinned, compiled upstream kitty.

This fixture executes upstream's native parser/model under REA on a disposable
Linux runner. It does not implement expected replies or create an OS window.
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


def make_cases():
    seed = b'\x1b[3;4H' + command('a=T,i=7,p=2,f=24,s=2,v=2,C=1', bytes((255, 0, 0)) * 4)
    cases = []

    def add(name, header, payload=None):
        cases.append((name, [('seed', seed), ('query', command(header, payload))]))

    def query(name, action='T', **keys):
        fields = dict(a='q', i=31, e=action, **keys)
        add(name, ','.join(f'{k}={v}' for k, v in fields.items()))

    for action in ('t', 'T', 'q', 'p', 'd', 'f', 'a', 'c', 'x'):
        query('action-' + action, action)
    for action in ('t', 'T', 'q', 'p', 'd', 'f', 'a', 'c', 'x'):
        query('action-keys-' + action, action, t='d', o='z', f=24, s=2, v=3,
              S=12, O=4, N=1, p=9, x=1, y=2, w=3, h=4, X=1, Y=2, c=3,
              r=4, C=1, U=1, z=-3, P=7, Q=2, H=-1, V=2, d='a')
    for fmt in (0, 8, 16, 24, 32, 100, 99):
        query('format-' + str(fmt), f=fmt)
    for medium in ('d', 'f', 't', 's', 'x'):
        query('medium-' + medium, t=medium)
    for compression in ('z', 'x'):
        query('compression-' + compression, o=compression)
    for key, values in [('C', (0, 1, 7)), ('U', (0, 1, 2)), ('N', (0, 1, 6))]:
        for value in values:
            query(f'flag-{key}-{value}', **{key:value})
    for dimension in (0, 1, 4096, 10000, 100000, 4294967295):
        query('dimensions-' + str(dimension), s=dimension, v=dimension)
    query('zero-fields', f=0, s=0, v=0, S=0, O=0, N=0, p=0, x=0, y=0,
          w=0, h=0, X=0, Y=0, c=0, r=0, C=0, U=0, z=0, P=0, Q=0, H=0, V=0)
    query('signed-limits', z=-2147483648, H=2147483647, V=-1)
    query('unsigned-limits', p=4294967295, S=4294967295, O=4294967295, X=4294967295)
    query('unknown-key', j=37)
    for selector in ('a', 'A', 'i', 'I', 'r', 'R', 'n', 'N', 'x', 'F', 'k'):
        query('delete-' + selector, 'd', d=selector, p=2, x=1, y=2, z=-1)
    for quiet in (0, 1, 2):
        add('quiet-' + str(quiet), f'a=q,i=31,e=T,C=1,q={quiet}')
    for name, header in [
        ('id-max', 'a=q,i=4294967295,e=T'),
        ('id-zero', 'a=q,i=0,e=T'),
        ('id-missing', 'a=q,e=T'),
        ('number-only', 'a=q,I=31,e=T'),
        ('id-and-number', 'a=q,i=31,I=7,e=T'),
        ('excluded-fields', 'a=q,i=31,I=7,e=T,m=1,q=0'),
        ('duplicate-action', 'a=q,i=31,e=T,e=p,C=1'),
        ('duplicate-value', 'a=q,i=31,e=T,C=7,C=1'),
        ('empty-action', 'a=q,i=31,e='),
        ('numeric-action', 'a=q,i=31,e=0'),
        ('nonquery-action', 'a=t,i=31,e=T,f=24,s=1,v=1'),
    ]:
        add(name, header, b'abc' if name == 'nonquery-action' else None)
    add('ignored-valid-payload', 'a=q,i=31,e=T,C=1', b'not an image')
    add('ignored-long-payload', 'a=q,i=31,e=T,C=1', b'x' * 6144)
    cases.append(('ignored-invalid-base64', [('seed', seed),
        ('query', b'\x1b_Ga=q,i=31,e=T,C=1;!@#$%\x1b\\')]))
    cases.append(('bytewise-query', [('seed', seed),
        ('query-bytewise', command('a=q,i=31,e=T,C=1,U=1,o=z,f=24'))]))
    for name, header in [('pending-query', 'a=q,i=31,e=T,C=1'),
                         ('pending-quiet-query', 'a=q,i=31,e=T,q=1'),
                         ('pending-unknown-action', 'a=q,i=31,e=x,C=1'),
                         ('pending-query-more-flag', 'a=q,i=31,e=T,m=1')]:
        cases.append((name, [('seed', seed),
            ('first-chunk', command('a=T,i=9,f=24,s=1,v=1,C=1,m=1', b'\x00\xff')),
            ('query', command(header, b'ignored')),
            ('last-chunk', command('m=0', b'\x00'))]))
    return cases


def main(inputs=None, family='kitty-features', fixture_path=__file__):
    import kitty.fast_data_types as native
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.graphics import TestGraphics
    from kitty_tests.main import env_for_python_tests

    source = Path(os.environ['NEMOTERM_KITTY_REFERENCE_SOURCE']).resolve()
    output = Path(os.environ['NEMOTERM_KITTY_REFERENCE_OUTPUT']).resolve()
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == UPSTREAM
    if inputs is None:
        inputs = make_cases()
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record = dict(status='running', family=family, upstream_commit=commit,
        scope='Native upstream query replies, cursor, images and layers; no OS window or GPU pixels',
        fixture_sha256=sha(fixture_path), observer_sha256=sha(__file__),
        platform=platform.platform(), python=platform.python_version(),
        source_sha256={p:sha(source/p) for p in ('kitty/graphics.c', 'kitty_tests/graphics.py', 'docs/graphics-protocol.rst')},
        compiled_sha256={p:sha(source/p) for p in ('kitty/launcher/kitty', str(Path(native.__file__).relative_to(source)))},
        expected_cases=[name for name, _ in inputs], cases=[])

    def save():
        output.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    save()
    with env_for_python_tests():
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([TestGraphics('test_load_images')]))
        record['upstream_tests'] = dict(names=['test_load_images'], run=result.testsRun,
            failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
            successful=result.wasSuccessful())
        save()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError('Upstream load/query tests did not all pass')
        for name, steps in inputs:
            helper = BaseTest()
            screen = helper.create_screen(COLS, ROWS, scrollback=20, cell_width=CW, cell_height=CH)
            case = dict(name=name, steps=[])
            record['cases'].append(case)
            try:
                for label, wire in steps:
                    screen.callbacks.clear()
                    chunks = [wire[i:i+1] for i in range(len(wire))] if label.endswith('-bytewise') else [wire]
                    for chunk in chunks:
                        parse_bytes(screen, chunk)
                    layers = screen.grman.update_layers(screen.scrolled_by, -1, 1,
                        2/COLS, 2/ROWS, COLS, ROWS, CW, CH)
                    case['steps'].append(dict(label=label, input_base64=base64.b64encode(wire).decode('ascii'),
                        chunk_bytes=[len(c) for c in chunks],
                        reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode('ascii'),
                        cursor=[screen.cursor.x, screen.cursor.y], image_count=screen.grman.image_count,
                        scrolled_by=screen.scrolled_by, layers=layers))
                    save()
                print('Captured feature query:', name, len(steps), 'states', flush=True)
            finally:
                screen.reset()
                helper.tearDown()
    record.update(status='complete', case_count=len(record['cases']),
                  state_count=sum(len(c['steps']) for c in record['cases']))
    save()
    print('Completed feature-query reference:', record['case_count'], record['state_count'], flush=True)


if __name__ == '__main__':
    main()
