"""Exercise the real caption fallback on an isolated CI desktop.

Only this Python controller's initial SetForegroundWindow call is replaced
with a refusal. The owned processes, queue barrier, caption hit test, SendInput,
foreground observation and complete bell assertions remain native and real.
"""
import json,os,runpy
from pathlib import Path
from unittest.mock import patch
assert os.environ.get('GITHUB_ACTIONS')=='true','Requires disposable CI desktop'
assert os.environ.get('NEMOTERM_FOCUS_MODE','synchronized')=='synchronized'
import owned_window_focus as focus

root=Path(__file__).resolve().parents[1]
record=dict(completed=False,denied_calls=[],scope='Controller-only refusal forces real owned caption input; no terminal API hooks or fabricated focus messages.')
record['double_click_ms']=focus.u.GetDoubleClickTime()
record['virtual_screen']=[focus.u.GetSystemMetrics(index) for index in (76,77,78,79)]
def refused(window):
    record['denied_calls'].append(dict(window=window,foreground=focus.u.GetForegroundWindow(),seconds=focus.time.monotonic()))
    return 0

try:
    with patch.object(focus.u,'SetForegroundWindow',refused):
        runpy.run_path(str(root/'tests/bell_window_state_smoke.py'),run_name='__main__')
    report=json.loads((root/'research/bell-window-state-observed.json').read_text(encoding='utf-8'))
    assert report['completed'] and len(report['checks'])==74
    assert record['denied_calls']
    clicked=[a for a in report['focus_actions'] if a['method']=='owned-caption-click']
    assert len(clicked)==len(record['denied_calls'])
    assert all(a['completed'] and a['after']==a['window'] for a in report['focus_actions'])
    assert all(not a['set_foreground_result'] and a['queue_barrier'] and
               a.get('cursor_restored') is not False for a in clicked)
    assert all(a['method'] in ('already-foreground','owned-caption-click') for a in report['focus_actions'])
    record.update(completed=True,executable_sha256=report['executable_sha256'],
                  native_caption_clicks=len(clicked),cursor_restored=sum(bool(a.get('cursor_restored')) for a in clicked),
                  checks=len(report['checks']))
    print('Real owned caption control:',len(clicked),'clicks; 74 bell-state checks passed')
except BaseException as error:
    record['error']=repr(error)
    raise
finally:
    (root/'research/owned-focus-caption-control.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
