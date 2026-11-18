"""Produce a same-image report from hosted interaction receipts for this attempt."""
import hashlib
import json
import os
from pathlib import Path
import sys

from interaction_acceptance import catalog

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from memory_limits import private_ws_passes


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def memory_case(path, row, renderer, executable):
    blobs = row['evidence']
    keys = [k for k in blobs if k.startswith('research/') and k.endswith('-memory.json')]
    require(len(keys) == 1, 'missing or ambiguous memory record')
    key, = keys
    meta_key = key[:-len('-memory.json')] + '-observed.json'
    # Select only a case-owned attempt. Do not resolve paths from the fixture log.
    matches = [p for p in (path/'interaction'/'attempts').glob(row['id']+'-*')
               if p.name == Path(row['directory']).name]
    require(len(matches) == 1, 'missing or ambiguous memory attempt')
    def checked(k):
        require(k == 'research/'+Path(k).name, 'unexpected memory record path')
        data = (matches[0]/k).read_bytes()
        require(hashlib.sha256(data).hexdigest() == blobs[k], 'memory record digest mismatch')
        return json.loads(data.decode('utf-8-sig'))
    observation, memory = checked(meta_key), checked(key)
    require(observation['executable_sha256'].lower() == executable and observation['completed']
            and observation['memory_instrumented'] is False and observation['exact_grid_passed']
            and observation['actual_grid'] == [160,48] and observation['actual_renderer'] == renderer,
            'wrong image, instrumentation, grid, or actual renderer')
    peak = memory['peaks']['frontend']
    require(private_ws_passes(renderer, peak['private_ws']) is True, 'private working set exceeds limit')
    return {k: peak[k] for k in ('private_ws','total_ws','private_commit')}


def main():
    e = os.environ
    scopes = [(json.loads(e['INDEPENDENT']), e['INDEPENDENT_STATUS']),
              (json.loads(e['SHELL_BACKED']), e['SHELL_STATUS'])]
    groups = [g for names,_ in scopes for g in names]
    errors = []
    result = dict(product_commit=e['PRODUCT_COMMIT'], product_run=e['PRODUCT_RUN'], fixture_commit=e['GITHUB_SHA'],
                  workflow_run=e['GITHUB_RUN_ID'], attempt=e['GITHUB_RUN_ATTEMPT'], groups={}, errors=errors)
    suffix = f"-{result['workflow_run']}-{result['attempt']}"
    images = set()
    for names,status in scopes:
        if names and status != 'success': errors.append(f'Group jobs {names}: {status}')
    all_cases = catalog()
    result['scope'] = 'all interaction groups' if set(groups) == {c['group'] for c in all_cases} else 'selected groups only'
    for group in groups:
        expected = [c['id'] for c in all_cases if c['group'] == group]
        stats = result['groups'][group] = dict(expected=expected, cases={}, artifact='interaction-'+group+suffix)
        try:
            path = Path('build/group-receipts')/('interaction-receipt-'+group+suffix)
            source, identity = read(path/'interaction-product/SOURCE-HOST.json'), read(path/'interaction/identity.json')
            exe = source['Executable']['SHA256'].lower()
            require(source['SourceCommit'] == result['product_commit'] and identity['fixture_commit'] == result['fixture_commit']
                    and exe == identity['executable_sha256'].lower() and source['Executable']['Bytes'] == identity['executable_bytes'],
                    'source, fixture or executable identity mismatch')
            images.add((exe, identity['executable_bytes']))
            rows = read(path/'interaction/results.json')
            for row in rows:
                case = row['id']
                require(case in expected and case not in stats['cases'], f'unexpected or duplicate case {case}')
                out = stats['cases'][case] = dict(status=row.get('status'), verified=False)
                try:
                    require(row['status'] == 'passed' and row['exit_code'] == 0 and row['cleanup']['terminated_remaining'] is False
                            and row['cleanup']['after']['active'] == 0 and row['cleanup']['remaining_processes'] == [],
                            'did not pass and exit naturally')
                    if group.startswith('memory-'):
                        out['frontend_peak_bytes'] = memory_case(path,row,{'memory-gdi':1,'memory-directx':3}[group],exe)
                    out['verified'] = True
                except (OSError, ValueError, TypeError, KeyError) as failure:
                    errors.append(f'{group}/{case}: {failure}')
            require(set(stats['cases']) == set(expected), f"missing cases: {sorted(set(expected)-stats['cases'].keys())}")
        except (OSError, ValueError, TypeError, KeyError) as failure:
            errors.append(f'{group}: {failure}')
    if len(images) != 1: errors.append('No single common executable identity')
    result['images'] = [dict(sha256=sha, bytes=size) for sha,size in sorted(images)]
    result['expected'] = sum(len(g['expected']) for g in result['groups'].values())
    result['verified'] = sum(c['verified'] for g in result['groups'].values() for c in g['cases'].values())
    result['passed'] = not errors and result['expected'] == result['verified'] and result['expected'] > 0
    dest = Path('build/interaction-report.json'); dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    note = [f"**{result['verified']}/{result['expected']} interaction cases verified** ({result['scope']}).",
            '', '| Group | Verified | Peak frontend private working set (bytes) |','|---|---:|---:|']
    for group,stats in result['groups'].items():
        rows = list(stats['cases'].values()); peak = max((v['frontend_peak_bytes']['private_ws'] for v in rows if 'frontend_peak_bytes' in v), default=None)
        note.append(f"| {group} | {sum(v['verified'] for v in rows)}/{len(stats['expected'])} | {peak if peak is not None else '—'} |")
    note += ['', *(f'- {v}' for v in errors), '', 'Original group artifacts contain the raw logs and screenshots. This report covers interaction only.']
    with open(e['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as stream: print('\n'.join(note),file=stream)
    print('\n'.join(note)); return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
