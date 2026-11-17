"""Render DPI evidence without treating requested scale as measured coverage."""
import argparse,json,os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',required=True,type=Path)
args=parser.parse_args()
root=args.evidence
root.mkdir(parents=True,exist_ok=True)
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
lines=['# Remote DPI evidence','',
    f'Product commit: `{os.environ.get("NEMOTERM_DPI_PRODUCT_COMMIT", "unavailable")}`',
    f'Fixture commit: `{os.environ.get("GITHUB_SHA", "local report")}`','',
    '## Real system scaling','',
    '| Language | Renderer | Host | Start | Test | Actual window DPI sequence | Result |',
    '|---|---|---|---:|---|---|---|']
real=list(root.glob('dpi-real-*.json'))
if not real:lines+=['| — | — | — | — | — | No real-system evidence | NOT RUN |']
gaps=[]
for path in real:
    result=read(path)
    for case in result['cases']:
        measured=', '.join(str(f['actual_host_dpi']) for f in case['frames']) or 'No measurement'
        lines.append(f'| {result.get("ui_language", "en")} | {result["renderer"]} | {case["host"]} | {case["start_percent"]}% | {"Live transition" if case["transition"] else "Cold start"} | {measured} | {"PASS" if case["completed"] else "FAIL"} |')
    if not result['completed']:lines+=['',f'**Real-system suite failed:** see `{path.name}` and its log.','']
    gaps+=result['coverage_gaps']
lines+=['','## Synthetic message coverage','',
    'These cases inject WM_DPICHANGED; the actual Windows DPI stays at 96. They are not real display-scale acceptance.','',
    '| Host | Requested DPI | Actual Windows DPI | Result |','|---|---|---|---|']
for mode in ('standalone','tabs'):
    files=list((root/f'synthetic-{mode}').glob('*input-method-observed.json'))
    path=next((p for p in files if p.name.startswith('tabs-')==(mode=='tabs')),None)
    if path:
        result=read(path)
        requested=', '.join(str(d['requested_dpi']) for d in result.get('dpi',[]))
        actual=', '.join(str(d['actual_window_dpi']) for d in result.get('dpi',[]))
        passed='synthetic-dpi-pixels-preserve-sixel' in result.get('checks',[])
        lines.append(f'| {mode} | {requested} | {actual} | {"PASS" if passed else "INCOMPLETE"} |')
        if isinstance(result.get('real_imm_submission'),str):gaps.append(result['real_imm_submission'])
    else:lines.append(f'| {mode} | — | — | NOT RUN |')
lines+=['','## Coverage limits','']+[f'- {gap}' for gap in dict.fromkeys(gaps)]
lines+=['','JSON, screenshots, display capabilities and executable identity are in the `dpi-evidence` artifact.','']
report='\n'.join(lines)
(root/'DPI-REPORT.md').write_text(report,encoding='utf-8')
if target:=os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(target,'a',encoding='utf-8') as output:output.write(report)
print(report)
