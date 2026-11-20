"""Review downloaded CI records for one binary; never run the binary or a fixture.

Usage: python scripts/review-frontend-memory.py SOURCE.zip AGENT.zip GDI.zip DX.zip
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile


METRICS = ('private_ws', 'total_ws', 'private_commit')
WORKLOADS = {'text','inline','animated','kitty','compressed-kitty','unicode-kitty'}
FONT = 'SarasaTermSC Nerd Light'
PTERM = '8580a3df4afe7696758c1cef43d0e88e3db5fd41c35c60166241aee72dd3ba3b'


def read(z, name):
    return json.loads(z.read(name).decode('utf-8-sig'))


def check(ok, reason):
    if not ok: raise ValueError(reason)


def stress(path, source, renderer, number, limit):
    with ZipFile(path) as z:
        check(read(z,'interaction-product/SOURCE-HOST.json')==source, 'source manifest: '+renderer)
        ident = read(z,'interaction/identity.json'); product = source['Executable']
        check(not ident['fixture_dirty'] and ident['executable_sha256']==product['SHA256'] and ident['executable_bytes']==product['Bytes'], 'interaction identity: '+renderer)
        cases = read(z,'interaction/results.json'); wanted = {'full-grid-'+w+'-'+renderer for w in WORKLOADS}
        check(len(cases)==len(wanted) and {c['id'] for c in cases}==wanted, 'workload inventory: '+renderer)
        result = {}
        for case in cases:
            name = case['id']; root = 'interaction/'+case['directory']+'/'
            check(case['status']=='passed' and not case['cleanup']['terminated_remaining'] and not case['cleanup']['remaining_processes'], 'lifetime: '+name)
            def evidence(suffix):
                key, = [k for k in case['evidence'] if k.endswith(suffix)]
                blob = z.read(root+key); check(sha256(blob).hexdigest()==case['evidence'][key], 'evidence digest: '+key)
                return json.loads(blob.decode('utf-8-sig'))
            obs = evidence('-observed.json'); mem = evidence('-memory.json')
            check(obs['completed'] and obs['executable_sha256']==product['SHA256'] and obs['actual_renderer']==number and obs['actual_grid']==[160,48] and obs['font']==FONT, 'renderer/grid/font: '+name)
            check(obs['memory_limit_passed'] and obs['memory_limit_required'] and obs['memory_limit_bytes']==limit and bool(obs['memory_limit_inclusive'])==(renderer=='directx'), 'gate: '+name)
            samples = mem['samples'];check(len(samples)==mem['sample_count'] and samples and not mem['errors'] and not mem['injected'] and not any(s['injected'] for s in samples), 'samples: '+name)
            frontend = [g for s in samples if (g:=s['groups'].get('frontend')) and g['count']]
            check(frontend and all(g['count']==1 for g in frontend),'frontend process: '+name)
            peak = {k:max(s[k] for s in frontend) for k in METRICS};check(all(peak[k]==mem['peaks']['frontend'][k] for k in METRICS),'peak mismatch: '+name)
            check(peak['private_ws']<=limit if renderer=='directx' else peak['private_ws']<limit, 'private working set exceeds limit: '+name)
            result[name] = dict(samples=len(frontend),peak=peak)
        return {'cases':result,'peak':{k:max(w['peak'][k] for w in result.values()) for k in METRICS}}


def conversation(path, source):
    with ZipFile(path) as z:
        check(read(z,'pair-product/SOURCE-HOST.json')==source, 'agent product manifest')
        summary = read(z,'paired-agent-memory/summary.json')
        check(summary['scenario']=='24-followups','agent scenario')
        result = {}; cases=summary['cases']
        check(set(cases)=={'1-pterm','2-nemoterm-tab','3-nemoterm-directx-tab'}, 'agent inventory')
        for name,c in cases.items():
            sha = PTERM if name=='1-pterm' else source['Executable']['SHA256']
            check(c['passed'] and c['terminal_sha256']==sha and c['profile']['Font']==FONT and c['console']['grid']==[160,48], 'agent identity: '+name)
            check(c['chat_requests']==25 and c['exit_code']==0 and not c['sample_errors'] and not c['provider_errors'] and not c['cleanup']['terminated_remaining'], 'agent session: '+name)
            check(c['native_runtime'] and all(r['exact_frontend_module'] and not r['matched_modules'] and not r['matched_processes'] for r in c['native_runtime']), 'sampled WebView indicators: '+name)
            check([x['stage'] for x in c['turns']]==[f'turn-{i:02d}' for i in range(1,25)] and all(x['memory']['samples'] for x in c['turns']), 'agent turns: '+name)
            samples = c['samples']
            check(bool(samples), 'missing raw agent process samples: '+name)
            peak = {key:max(sample[key] for sample in samples) for key in METRICS}
            check(peak==c['whole_run_peak'], 'raw agent peak mismatch: '+name)
            if name != '1-pterm':
                renderer = 1 if name=='2-nemoterm-tab' else 3
                check(c['renderer_before']==c['renderer_after']==renderer and
                      all(turn['actual_renderer']==renderer for turn in c['turns']), 'agent renderer changed: '+name)
                check(peak['private_ws']<20_000_000 if renderer==1 else peak['private_ws']<=30_000_000,
                      'agent private working set exceeds limit: '+name)
            result[name] = {'whole_run_peak':peak, 'samples':len(samples), 'empty_median':c['empty']['median'],
                            'last_turn_median':c['turns'][-1]['memory']['median']}
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','agent','gdi','directx'): p.add_argument(k,type=Path)
    p.add_argument('--summary',type=Path,help='Append a Markdown table to a GitHub job summary')
    a=p.parse_args()
    with ZipFile(a.source) as z:
        m=read(z,'SOURCE-HOST.json');product=z.read('nemoterm.exe')
        check(m['Executable']=={'SHA256':sha256(product).hexdigest(),'Bytes':len(product)}, 'product bytes')
    r={'commit':m['SourceCommit'],'executable':m['Executable'],'conversation':conversation(a.agent,m),
       'gdi':stress(a.gdi,m,'gdi',1,20_000_000),'directx':stress(a.directx,m,'directx',3,30_000_000)}
    if a.summary:
        rows=[(label,r['conversation'][key]['whole_run_peak']) for key,label in
              [('1-pterm','pterm'),('2-nemoterm-tab','GDI'),('3-nemoterm-directx-tab','DirectX')]]
        rows=[(label+' / 24 Codex turns',peak) for label,peak in rows]
        rows.extend((label+' / six 160×48 workloads',r[key]['peak']) for key,label in [('gdi','GDI'),('directx','DirectX')])
        with a.summary.open('a',encoding='utf-8') as f:
            print(f"Frontend process peaks in bytes; EXE `{m['Executable']['SHA256']}`.\n",file=f)
            print('| Workload | Private working set | Total working set | Private commit |\n|---|---:|---:|---:|',file=f)
            for label,peak in rows:
                print('| '+label+' | '+' | '.join(f'{peak[k]:,}' for k in METRICS)+' |',file=f)
    print(json.dumps(r,indent=2))
