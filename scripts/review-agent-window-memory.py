"""Review recorded frontend working sets during real selection, copy and submission."""
import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from zipfile import ZipFile


METRICS = ('private_ws', 'total_ws', 'private_commit')
CLIENTS = ('codex', 'claude', 'opencode')
LIMITS = {'gdi': 20_000_000, 'directx': 30_000_000}


def need(ok, detail):
    if not ok:
        raise ValueError(detail)


def review(receipt):
    def read(path):
        return json.loads(z.read(path).decode('utf-8-sig'))
    cases = {}
    with ZipFile(receipt) as z:
        ident = read('interaction/identity.json'); source = read('interaction-product/SOURCE-HOST.json')
        exe = source['Executable']; font = 'SarasaTermSC Nerd Light'
        need(exe == {'SHA256': ident['executable_sha256'], 'Bytes': ident['executable_bytes']} and
             ident['font'] == font and not ident['fixture_dirty'], 'product or font differs')
        wants = {f'agent-grid-{variant}-{renderer}': (variant.split('-')[0], renderer)
                 for renderer in LIMITS for variant in (*CLIENTS, 'claude-shell', 'claude-visual-order')}
        for case in read('interaction/results.json'):
            name = case['id']; client, renderer = wants[name]
            need(name not in cases and case['status']=='passed' and not case['cleanup']['terminated_remaining'], name)
            key, = [k for k in case['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]
            raw = z.read(f"interaction/{case['directory']}/{key}"); digest = sha256(raw).hexdigest()
            need(digest==case['evidence'][key], name+' receipt digest'); obs = json.loads(raw)
            child=obs['child']; seat=obs['session']; trace=obs['frontend_trace']; events=obs['frontend_samples']
            need(obs['completed'] and obs['requested_renderer']==renderer and seat['active'] and
                 seat['renderer']=={'gdi':0,'directx':2}[renderer] and (seat['cols'],seat['rows'])==(160,48) and
                 child['hwnd']==seat['hwnd'] and obs['font']==font and obs['client']==child['client']==client and
                 child['terminal_sha256']==exe['SHA256'] and child['client_sha256']==ident['clients'][client]['sha256'],name+' identity')
            need([(r['phase'],r['frontend_pid'],r['exact_frontend_module']) for r in obs['native_runtime']]==
                 [('startup',child['pid'],True),('submitted',child['pid'],True)], name+' frontend process')
            need([s['phase'] for s in events]==['startup','reply','copy','composer','submitted'] and
                 trace['start']=='session discovered' and trace['stop']=='after submitted reply or failure' and
                 trace['requested_interval_ms']==100 and not trace['errors'], name+' sampling coverage')
            samples=trace['samples']; times=[s['seconds'] for s in samples]
            need(len(times)>=2 and all(isfinite(t) and t>=0 for t in times) and
                 all(a<b for a,b in zip(times,times[1:])), name+' sample times')
            all_samples=events+samples
            need(all(type(s[k]) is int and s[k]>0 for s in all_samples for k in METRICS) and
                 all(s['private_ws']<=s['total_ws'] for s in all_samples),name+' invalid counters')
            peak={k:max(s[k] for s in all_samples) for k in METRICS}; limit=LIMITS[renderer]
            cases[name]=dict(client=client,renderer=renderer,sha256=digest,frontend_pid=child['pid'],samples=len(samples),
                phase_samples=len(events),seconds=times[-1]-times[0],max_gap_ms=max(b-a for a,b in zip(times,times[1:]))*1000,
                peaks=peak,private_ws_limit=limit,within_limit=(peak['private_ws']<limit if renderer=='gdi' else peak['private_ws']<=limit))
        need(set(cases)==set(wants), 'missing named agent windows')
    pairs={client:{r:{k:max(c['peaks'][k] for c in cases.values() if c['renderer']==r and c['client']==client)
                      for k in METRICS} for r in LIMITS} for client in CLIENTS}
    return dict(source=source['SourceCommit'],fixture=ident['fixture_commit'],executable=exe,font=font,cases=cases,by_client=pairs)


def markdown(report):
    s=['真实应用窗口的前端私有工作集（十进制 MB）','', '| 客户端 | GDI | DirectX |','| --- | ---: | ---: |']
    for client,renderers in report['by_client'].items():
        s.append(f"| {client} | {renderers['gdi']['private_ws']/1e6:.2f} | {renderers['directx']['private_ws']/1e6:.2f} |")
    n=sum(r['samples'] for r in report['cases'].values()); phases=sum(r['phase_samples'] for r in report['cases'].values())
    s.extend(['',f'从发现窗口到提交回复：{n} 次定时采样，另有 {phases} 次操作节点采样。只计终端前端，不含 agent 和控制台宿主。取所有对应窗口的实测最大值；采样之间的瞬时峰值未知。'])
    return '\n'.join(s)+'\n'


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('receipt',type=Path);cli.add_argument('output',type=Path)
    args=cli.parse_args(); result=review(args.receipt);args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    args.output.with_suffix('.md').write_text(markdown(result),encoding='utf8');print(markdown(result))
    raise SystemExit(0 if all(c['within_limit'] for c in result['cases'].values()) else 1)
