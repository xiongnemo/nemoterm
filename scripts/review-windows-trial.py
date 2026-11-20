"""Assemble one hosted trial report from byte-verified archives. Never run the EXE."""
import argparse
from hashlib import sha256
from importlib.util import spec_from_file_location, module_from_spec
import json
import os
from pathlib import Path
from zipfile import ZipFile


def reviewer(name):
    spec = spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module


def read(archive, member):
    return json.loads(archive.read(member).decode('utf-8-sig'))


def check(condition, message):
    if not condition: raise ValueError(message)


def collect(run, commit, directory):
    directory.mkdir(parents=True, exist_ok=False)
    raw = directory/'sources'; out = directory/'report'; out.mkdir()
    archives = dict(agents='interaction-agents', shortcuts='interaction-receipt-agents', grid='interaction-agents-grid',
                    windows='interaction-receipt-agents-grid', strict='interaction-report',
                    vim='wsl-vim', tmux='wsl-tmux-vim', sixel='wsl-sixel')
    reviewer('fetch-memory-review').fetch(run, commit, raw, extra_archives=archives)
    (out/'inputs.json').write_bytes((raw/'inputs.json').read_bytes())
    archive = lambda key: raw/(key+'.zip')
    with ZipFile(archive('source')) as z:
        source = read(z,'SOURCE-HOST.json'); exe = source['Executable']
        image = z.read('nemoterm.exe'); check(exe == {'Bytes':len(image),'SHA256':sha256(image).hexdigest()}, 'EXE identity')
    with ZipFile(archive('strict')) as z: strict = read(z,'interaction-report.json')
    check(strict['product_commit']==strict['fixture_commit']==commit and int(strict['product_run'])==run and
          strict['scope']=='all interaction groups' and strict['images']==[{'sha256':exe['SHA256'],'bytes':exe['Bytes']}], 'strict interaction source or scope')
    failed=[]; absent=[]; unique=set(); verified=0
    for name,group in strict['groups'].items():
        expected=group['expected']; cases=group['cases']
        check(len(set(expected))==len(expected) and not unique.intersection(expected) and set(cases)<=set(expected),'case inventory: '+name)
        unique.update(expected); absent.extend(sorted(set(expected)-cases.keys()))
        for case,result in cases.items():
            if result['verified'] and result['status']=='passed': verified+=1
            else: failed.append(case)
    check(strict['expected']==len(unique) and strict['verified']==verified and
          strict['passed']==(not strict['errors'] and verified==len(unique) and verified>0), 'strict counts')
    (out/'original-interaction-report.json').write_text(json.dumps(strict,indent=2),encoding='utf8')
    # The existing reviewers check raw pixel crops, clipboard, actual renderer, provider
    # submissions, per-process samples and executable identities before returning.
    mem = reviewer('review-frontend-memory')
    conversation = mem.conversation(archive('conversation'),source)
    stress = {r:mem.stress(archive(r),source,r,n,limit) for r,n,limit in [('gdi',1,20_000_000),('directx',3,30_000_000)]}
    binding = reviewer('review-agent-bindings').review(archive('shortcuts'),archive('agents'))
    check(binding['source']==commit and binding['executable']==exe and len(binding['cases'])==18,'clipboard review identity')
    for key in ('windows','grid','shortcuts','agents'):
        with ZipFile(archive(key)) as z:
            ident = read(z,'interaction/identity.json')
            check(read(z,'interaction-product/SOURCE-HOST.json')==source and ident['fixture_commit']==commit and
                  ident['font']=='SarasaTermSC Nerd Light' and not ident['fixture_dirty'],'window fixture: '+key)
    reviewer('review-agent-wide-selection').review(archive('windows'),archive('grid'),out/'selection')
    reviewer('review-agent-composer').review(archive('windows'),archive('grid'),out/'composer')
    paste = reviewer('review-codex-paste-receipts').review(archive('agents'),commit)
    check(paste['executable']==exe and paste['fixture_commit']==commit,'image paste identity')
    graphics=reviewer('review-wsl-window-records').review(archive('vim'),archive('tmux'),archive('sixel'))
    check(graphics['product']==commit and graphics['exe']==exe['SHA256'],'graphics identity')
    data=dict(product=source,run=run,bindings=binding,images=paste,windows=graphics,conversation=conversation,stress=stress,
              interaction=dict(verified=verified,expected=len(unique),failed=failed,not_run=absent,passed=strict['passed']))
    (out/'records.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    base=f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{run}'
    inputs=json.loads((out/'inputs.json').read_bytes())['archives']; source_id=inputs['source']['id']
    lines=[f'# Windows x64 试用验收：`{commit[:8]}`','',f'[单文件 EXE]({base}/artifacts/{source_id}) · [原始完整运行]({base})',
           f'文件：{exe["Bytes"]:,} 字节，SHA-256 `{exe["SHA256"]}`。','',
           f'严格交互：**{verified}/{len(unique)}**。未通过：{", ".join(failed) or "无"}。未执行：{", ".join(absent) or "无"}。',
           '全文按原始结果计分；完整运行还包括此报告未覆盖的协议和平台测试。','',
           '| 前端 / 负载 | 私有工作集峰值（字节） | 总工作集峰值（字节） | 私有提交峰值（字节） |','|---|---:|---:|---:|']
    rows=[(label+' / 24 轮 Codex',conversation[key]['whole_run_peak']) for label,key in [('pterm','1-pterm'),('GDI','2-nemoterm-tab'),('DirectX','3-nemoterm-directx-tab')]]
    rows += [(label+' / 六种满屏负载',stress[key]['peak']) for label,key in [('GDI','gdi'),('DirectX','directx')]]
    lines += ['| '+label+' | '+' | '.join(f'{m[k]:,}' for k in mem.METRICS)+' |' for label,m in rows]
    lines += ['', 'Codex、Claude Code、OpenCode：18/18 项快捷键和右键行为通过。10 个窗口的实际 Shift 选区都复制出「中文」；选区及相邻字格见附件 `selection/selected.png`。',
              'GDI 和 DirectX 的 8 帧 Sixel 已核对。字体为 SarasaTermSC Nerd Light。','',
              '| Codex 粘贴时机 | 输入方式 | Ctrl+V 首次提交 | Ctrl+Shift+V 首次提交 | 原始用例结果 |','|---|---|---|---|---|']
    for row in paste['cases'].values():
        cols=[row['phase'],row['input'],*(row['shortcuts'][k]['first_submission'] for k in ('ctrl-v','ctrl-shift-v')),row['fixture_status']]
        lines.append('| '+' | '.join(cols)+' |')
    text='\n'.join(lines)+'\n'; (out/'report.md').write_text(text,encoding='utf8')
    if summary:=os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary,'a',encoding='utf8') as stream:stream.write(text)
    return strict['passed'] and all(row['fixture_status']=='passed' and all(x['passed'] for x in row['shortcuts'].values()) for row in paste['cases'].values())


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('run',type=int);cli.add_argument('commit');cli.add_argument('directory',type=Path)
    args=cli.parse_args();raise SystemExit(0 if collect(args.run,args.commit,args.directory) else 1)
