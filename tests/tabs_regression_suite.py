"""Run the existing native protocol checks inside the optional tab host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
cases = [(f'overflow-{side}', 'tabs_overflow', ['--side', side], None)
         for side in ('top', 'bottom', 'left', 'right')]
cases += [
    ('profiles', 'tabs_profiles', [], None),
    ('geometry', 'geometry', ['--tabs', '--tab-side', 'bottom'], None),
    ('window-resize', 'window_resize', ['--tabs', '--tab-side', 'left'], None),
    ('input-method', 'input_method', ['--tabs'] +
        (['--font', 'Consolas'] if os.environ.get('CI') == 'true' else []), None),
]
cases += [(f'selection-{name}', 'selection', ['--tabs', '--tab-side', 'right',
           '--renderer', str(renderer)], 'tabs-selection-observed.json')
          for renderer, name in ((0, 'gdi'), (1, 'opengl'), (2, 'directx'))]
evidence = dict(completed=False, checks=[])
try:
    for name, script, args, record in cases:
        log = root/'research'/f'tabs-{name}.log'
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run([sys.executable,
                str(root/'tests'/f'{script}_window_smoke.py'), *args],
                stdout=stream, stderr=subprocess.STDOUT)
        if record and (root/'research'/record).exists():
            shutil.copyfile(root/'research'/record,
                            root/'research'/f'tabs-{name}-observed.json')
        if result.returncode:
            print(log.read_text(encoding='utf-8')[-5000:], flush=True)
            raise RuntimeError(f'Tab regression failed: {name} ({result.returncode})')
        evidence['checks'].append(name)
        print(f'Tab regression passed: {name}', flush=True)
    evidence['completed'] = True
finally:
    if sys.exc_info()[0]:
        evidence['error'] = repr(sys.exc_info()[1])
    (root/'research/tabs-regressions-observed.json').write_text(
        json.dumps(evidence, indent=2), encoding='utf-8')
