"""Capture upstream cell-image rectangles for native font-size comparisons.

All screens receive exactly the same bytes. Cell geometry is an explicit
construction input, not a calculated expected image box. No Nemoterm executes.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import unittest

UPSTREAM = '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
CONTROLS = ['test_unicode_placeholders', 'test_unicode_placeholders_multiple_placements', 'test_image_parents']


def wire():
    text = ''
    marks = ['\u0305', '\u030d', '\u030e', '\u0310']
    for ident, column, colour in [(1, 2, (255, 0, 0)), (2, 15, (0, 0, 255))]:
        text += '\x1b_G' + f'a=T,i={ident},p=7,f=24,s=32,v=48,c=4,r=3,U=1,C=1;'
        text += base64.b64encode(bytes(colour)*32*48).decode() + '\x1b\\'
        text += '\x1b[38;5;' + str(ident) + 'm'
        for row in range(3):
            text += '\x1b[' + f'{row+3};{column+1}H'
            text += ''.join('\U0010eeee' + marks[row] + marks[col] for col in range(4))
    return (text + '\x1b[H').encode()


def main():
    import kitty.fast_data_types as native
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.graphics import TestGraphics
    from kitty_tests.main import env_for_python_tests
    source = Path(os.environ['NEMOTERM_KITTY_REFERENCE_SOURCE']).resolve()
    output = Path(os.environ['NEMOTERM_KITTY_REFERENCE_OUTPUT']).resolve()
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == UPSTREAM
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record = dict(status='running', family='kitty-unicode-geometry', upstream_commit=UPSTREAM,
        fixture_sha256=sha(__file__), input_base64=base64.b64encode(wire()).decode(),
        source_image=dict(width=32,height=48,columns=4,rows=3),
        scope='Fresh upstream cell-image rectangles at explicit font cell sizes; no GPU pixel or incremental font-rescale claim',
        observation_effects=['update_only_line_graphics_data','update_layers'],
        declared_actions=['create fresh screen with specified cell width/height','fixed VT byte input'],
        source_sha256={p:sha(source/p) for p in ('kitty/graphics.c','kitty/shaders.c','kitty_tests/graphics.py')},
        compiled_sha256={p:sha(source/p) for p in ('kitty/launcher/kitty',str(Path(native.__file__).relative_to(source)))},
        platform=platform.platform(), python=platform.python_version(), cases=[])
    save = lambda: output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    save()
    with env_for_python_tests():
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(TestGraphics(n) for n in CONTROLS))
        record['upstream_tests']=dict(names=CONTROLS,run=result.testsRun,successful=result.wasSuccessful(),skipped=len(result.skipped))
        save()
        assert result.wasSuccessful() and not result.skipped
        for cw in range(4,13):
            for ch in range(10,27):
                helper=BaseTest();screen=helper.create_screen(40,12,scrollback=20,cell_width=cw,cell_height=ch)
                try:
                    parse_bytes(screen,wire());screen.update_only_line_graphics_data()
                    layers=screen.grman.update_layers(0,-1,1,2/40,2/12,40,12,cw,ch)
                    record['cases'].append(dict(name=f'{cw}x{ch}',cell_width=cw,cell_height=ch,
                        columns=40,rows=12,layers=layers,reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode(),
                        cursor=[screen.cursor.x,screen.cursor.y],image_count=screen.grman.image_count,
                        text=[str(screen.line(y)) for y in range(screen.lines)]))
                finally:
                    screen.reset();helper.tearDown()
            save();print('Captured font cell width:',cw,flush=True)
    record.update(status='complete',case_count=len(record['cases']),state_count=len(record['cases']))
    assert record['case_count']==153
    save();print('Completed 153 independent cell geometries',flush=True)


if __name__=='__main__':main()
