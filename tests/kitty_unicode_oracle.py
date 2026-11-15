"""Record Unicode-image behavior in the pinned compiled upstream, under REA.

Inputs are independently authored VT bytes and explicitly declared resize/view
operations. All replies, cells and raw layers come from upstream; this fixture
does not calculate expected placement geometry or execute Nemoterm.
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
CONTROLS = ['test_unicode_placeholders', 'test_unicode_placeholders_3rd_combining_char',
    'test_unicode_placeholders_multiple_placements', 'test_unicode_placeholders_scroll',
    'test_unicode_placeholders_reverse_scroll', 'test_unicode_placeholders_history_margins',
    'test_unicode_placeholders_history_fill', 'test_image_parents']


def command(header, payload=None):
    return b'\x1b_G' + header.encode('ascii') + (b';' + base64.b64encode(payload) if payload is not None else b'') + b'\x1b\\'


def upload(image=42, width=20, height=20, **fields):
    keys = dict(a='T', f=24, i=image, s=width, v=height, U=1, c=4, r=2, C=1)
    keys.update(fields)
    return command(','.join(f'{k}={v}' for k, v in keys.items()), bytes((19, 137, 241)) * width * height)


def read_diacritics(path):
    return [chr(int(line.split(';')[0], 16)) for line in Path(path).read_text().splitlines()
            if line and not line.startswith('#')]


def make_cases(diacritics):
    def cell(*indices):
        return ('\U0010eeee' + ''.join(diacritics[i] for i in indices)).encode()

    def at(row, col):
        return f'\x1b[{row + 1};{col + 1}H'.encode()

    def step(label, wire=b'', **operation):
        return dict(label=label, wire=wire, **operation)

    fg = b'\x1b[38;5;42m'
    pair = cell(0, 0) + cell(0, 1)
    cases = []

    def add(name, steps, seed=None):
        cases.append((name, [step('seed', upload() if seed is None else seed), *steps]))

    for name, fields in [
        ('natural', dict(c=0, r=0)), ('columns-only', dict(c=3, r=0)),
        ('rows-only', dict(c=0, r=3)), ('fit-wide', dict(c=5, r=1)),
        ('fit-tall', dict(c=1, r=4)), ('cursor-zero', dict(C=0)),
        ('pixel-offset', dict(X=4, Y=7)), ('crop', dict(x=4, y=3, w=8, h=9)),
        ('positive-layer', dict(z=7)), ('negative-layer', dict(z=-9)),
        ('nonboolean-U', dict(U=2)), ('quiet', dict(q=2)),
    ]:
        add('virtual-' + name, [step('cells', fg + pair), step('erase', b'\x1b[2J')],
            at(2, 3) + upload(**fields) + at(0, 0))

    for name, colour in [('indexed', fg), ('rgb', b'\x1b[38;2;0;0;42m'),
                         ('rgb-colon', b'\x1b[38:2::0:0:42m'), ('default', b'\x1b[39m'),
                         ('missing', b'\x1b[38;5;43m'), ('basic-colour', b'\x1b[32m')]:
        add('identity-' + name, [step('cells', colour + pair), step('reset-colour', b'\x1b[39m' + cell())])
    for high in (0, 1, 42, 255):
        add('high-byte-' + str(high), [step('explicit', fg + cell(0, 0, high)),
            step('inherit-all', cell()), step('inherit-column-byte', cell(0)),
            step('inherit-byte', cell(0, 3)), step('changed-row', cell(1))],
            upload(image=(high << 24) + 42))

    patterns = [
        ('no-marks-first', cell() * 4), ('row-first', cell(0) + cell() * 3),
        ('mixed', cell(0, 0) + cell(0) + cell() + cell(0, 3)),
        ('changed-row', cell(0, 0) + cell(1) + cell() * 2),
        ('discontinuous-column', cell(0, 0) + cell(0, 2) + cell()),
        ('ordinary-gap', cell(0, 0) + b'x' + cell()),
        ('changed-foreground', cell(0, 0) + b'\x1b[38;5;43m' + cell()),
        ('changed-underline', cell(0, 0) + b'\x1b[58;5;7m' + cell()),
        ('changed-background', cell(0, 0) + b'\x1b[48;5;1m' + cell()),
        ('changed-attributes', cell(0, 0) + b'\x1b[1;3;4;7m' + cell()),
        ('unrecognised-mark-first', '\U0010eeee\u0301'.encode() + diacritics[0].encode() * 2),
        ('unrecognised-mark-between', cell(0) + '\u0301'.encode() + diacritics[1].encode()),
        ('extra-fourth-mark', cell(0, 0, 0, 42) + cell()),
        ('supplementary-mark', cell(0, 0) + '\U0001d185'.encode() + cell()),
        ('variation-selector', cell(0, 0) + '\ufe0f'.encode() + cell()),
    ]
    for name, wire in patterns:
        add('inheritance-' + name, [step('cells', fg + wire), step('erase-middle', at(0, 1) + b'\x1b[X')])

    add('all-diacritic-indices', [step('index-' + str(i), at(0, 0) + fg + cell(i, i))
        for i in range(len(diacritics))], upload(width=10, height=20, c=len(diacritics), r=len(diacritics)))
    add('incremental-combining', [step('base', fg + cell()), step('row', diacritics[1].encode()),
        step('column', diacritics[2].encode()), step('byte', diacritics[0].encode()),
        step('extra', diacritics[3].encode()), step('next', cell())])

    templates = upload(p=1, c=1, r=1) + command('a=p,i=42,U=1,p=22,c=2,r=1') + command('a=p,i=42,U=1,p=44,c=4,r=2')
    for name, colour in [('default', b'\x1b[59m'), ('zero', b'\x1b[58;5;0m'),
        ('one', b'\x1b[58;5;1m'), ('twenty-two', b'\x1b[58;5;22m'),
        ('rgb-forty-four', b'\x1b[58;2;0;0;44m'), ('missing', b'\x1b[58;5;99m')]:
        add('placement-colour-' + name, [step('cells', fg + colour + pair),
            step('replace-template', command('a=p,i=42,U=1,p=22,c=4,r=3'))], templates)

    editing = [('overwrite', b'x'), ('ech', b'\x1b[X'), ('el-right', b'\x1b[K'),
        ('el-left', b'\x1b[1K'), ('el-all', b'\x1b[2K'), ('ed-right', b'\x1b[J'),
        ('ed-left', b'\x1b[1J'), ('ed-all', b'\x1b[2J'), ('delete-character', b'\x1b[P'),
        ('insert-character', b'\x1b[@'), ('insert-mode', b'\x1b[4hx\x1b[4l'),
        ('delete-line', b'\x1b[M'), ('insert-line', b'\x1b[L'),
        ('scroll-up', b'\x1b[S'), ('scroll-down', b'\x1b[T')]
    grid = fg + pair + b'\r\n' + cell(1, 0) + cell(1, 1)
    for name, wire in editing:
        add('edit-' + name, [step('grid', grid), step('edit', at(0, 1) + wire),
            step('refresh', b''), step('erase', b'\x1b[2J')])
    add('repeat-placeholder', [step('repeat', fg + cell(0, 0) + b'\x1b[3b'),
        step('erase-first', at(0, 0) + b'\x1b[X')])
    add('wrap', [step('across-wrap', at(0, COLS - 1) + fg + pair + cell()),
        step('next-row', b'\r\n' + cell(1) + cell())])
    add('wide-text-neighbour', [step('cells', fg + '界'.encode() + pair),
        step('overwrite-wide-half', at(0, 1) + cell(1, 0))])

    for action in 'acpqxyzirnACPQXYZIRN':
        header=f'a=d,d={action},x=1,y=1,z=-1'
        if action.lower() == 'r': header=f'a=d,d={action},x=42,y=42'
        if action.lower() == 'n': header=f'a=d,d={action},I=9'
        if action.lower() in 'ai': header=f'a=d,d={action},i=42,p=7'
        seed=upload(p=7) if action.lower() != 'n' else upload(image=0, I=9, p=7)
        colour=fg if action.lower() != 'n' else b'\x1b[38;5;1m'
        add('delete-' + action, [step('cells', colour + pair), step('delete', command(header)),
            step('refresh', b''), step('redraw', at(1, 1) + colour + pair),
            step('place-after-delete', command('a=p,i=42,U=1,p=7,c=4,r=2'))], seed)

    add('retransmission', [step('cells', fg + pair), step('replace-data', upload(a='t')),
        step('recreate-template', command('a=p,i=42,U=1,c=4,r=2')), step('erase', b'\x1b[2J')])
    add('ordinary-to-virtual', [step('ordinary', upload(U=0, p=7)), step('cells', fg + pair),
        step('virtual', command('a=p,i=42,p=7,U=1,c=4,r=2'))])
    add('virtual-to-ordinary', [step('cells', fg + pair),
        step('ordinary', command('a=p,i=42,p=7,U=0,C=1')), step('erase', b'\x1b[2J')], upload(p=7))
    add('virtual-child-visibility', [step('child', upload(image=2, a='t') + command('a=p,i=2,p=9,P=42,H=1,V=2')),
        step('later-anchor', at(2, 3) + fg + pair), step('earlier-anchor', at(0, 0) + fg + pair),
        step('erase-first', at(0, 0) + b'\x1b[2K'), step('erase-all', b'\x1b[2J'),
        step('redraw', at(1, 1) + fg + pair)])
    for mode in (47, 1047, 1049):
        add('alternate-' + str(mode), [step('main-cells', fg + pair),
            step('enter', f'\x1b[?{mode}h'.encode()), step('alternate-cells', upload() + fg + pair),
            step('leave', f'\x1b[?{mode}l'.encode()), step('erase-main', b'\x1b[2J')])
    for name, wire in [('soft-reset', b'\x1b[!p'), ('hard-reset', b'\x1bc'),
                       ('erase-history', b'\x1b[3J'), ('save-restore', b'\x1b7\x1b[0m\x1b8' + cell())]:
        add(name, [step('cells', fg + pair), step('operation', wire), step('redraw', at(1, 0) + fg + pair)])

    for margins in (False, True):
        prefix=b'\x1b[1;7r' if margins else b''
        bottom=6 if margins else 7
        add('history-' + ('margin' if margins else 'full'), [step('grid', prefix + at(1, 0) + grid),
            step('into-history', at(bottom, 0) + b'\r\n' * 8), step('view-history', scroll=[6, True]),
            step('view-bottom', scroll=[6, False]), step('more-output', at(bottom, 0) + b'\r\n' * 4),
            step('view-older', scroll=[10, True]), step('erase-history', b'\x1b[3J')])
    add('resize-reflow', [step('wrapped-cells', fg + pair * 10), step('narrow', resize=[8, 6]),
        step('wide', resize=[8, 18]), step('tall', resize=[12, 18]), step('short', resize=[5, 18]),
        step('view-history', scroll=[5, True]), step('restore', resize=[8, 12])])
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
    table=read_diacritics(source/'gen/rowcolumn-diacritics.txt')
    inputs=make_cases(table)
    sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record=dict(status='running', family='kitty-unicode', upstream_commit=commit,
        scope='Compiled upstream Unicode image cells, lifecycle and replies; no OS window/GPU pixels',
        observation_effects=['update_only_line_graphics_data', 'update_layers'],
        declared_actions=['VT byte input', 'screen.resize(rows, columns)', 'screen.scroll(amount, up)'],
        fixture_sha256=sha(__file__), platform=platform.platform(), python=platform.python_version(),
        source_sha256={p:sha(source/p) for p in ('kitty/graphics.c', 'kitty_tests/graphics.py',
            'docs/graphics-protocol.rst', 'gen/rowcolumn-diacritics.txt')},
        compiled_sha256={p:sha(source/p) for p in ('kitty/launcher/kitty', str(Path(native.__file__).relative_to(source)))},
        geometry=dict(columns=COLS, rows=ROWS, cell_width=CW, cell_height=CH),
        diacritic_codepoints=[ord(c) for c in table], expected_cases=[name for name,_ in inputs], cases=[])

    def save():
        output.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    save()
    with env_for_python_tests():
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(TestGraphics(n) for n in CONTROLS))
        record['upstream_tests']=dict(names=CONTROLS, run=result.testsRun, failures=len(result.failures),
            errors=len(result.errors), skipped=len(result.skipped), successful=result.wasSuccessful())
        save()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError('Upstream Unicode/parent controls did not all pass')
        for name,steps in inputs:
            helper=BaseTest()
            screen=helper.create_screen(COLS, ROWS, scrollback=20, cell_width=CW, cell_height=CH)
            case=dict(name=name, steps=[]);record['cases'].append(case)
            try:
                for event in steps:
                    screen.callbacks.clear()
                    if 'resize' in event: screen.resize(*event['resize'])
                    if 'scroll' in event: screen.scroll(*event['scroll'])
                    parse_bytes(screen,event['wire'])
                    before_layers=screen.grman.image_count
                    screen.update_only_line_graphics_data()
                    layers=screen.grman.update_layers(screen.scrolled_by,-1,1,
                        2/screen.columns,2/screen.lines,screen.columns,screen.lines,CW,CH)
                    case['steps'].append(dict(label=event['label'], input_base64=base64.b64encode(event['wire']).decode(),
                        operation={k:v for k,v in event.items() if k not in ('label','wire')},
                        reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode(),
                        cursor=[screen.cursor.x,screen.cursor.y], image_count=screen.grman.image_count,
                        image_count_before_layers=before_layers, scrolled_by=screen.scrolled_by,
                        geometry=dict(columns=screen.columns,rows=screen.lines,cell_width=CW,cell_height=CH),
                        text=[str(screen.line(y)) for y in range(screen.lines)], layers=layers))
                    save()
                print('Captured Unicode images:',name,len(steps),'states',flush=True)
            finally:
                screen.reset();helper.tearDown()
    record.update(status='complete',case_count=len(record['cases']),
        state_count=sum(len(c['steps']) for c in record['cases']))
    save()
    print('Completed Unicode-image reference:',record['case_count'],record['state_count'],flush=True)


if __name__=='__main__':
    main()
