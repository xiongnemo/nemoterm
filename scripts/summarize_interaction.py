"""Produce a same-image report from hosted interaction receipts for this attempt."""
import hashlib
import json
import os
from pathlib import Path
import sys

from interaction_acceptance import catalog

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from memory_limits import private_ws_passes
from agent_image_receipt import chat_attachment


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def record_reader(path,row):
    blobs=row['evidence']
    # Select only a case-owned attempt. Do not resolve paths from the fixture log.
    matches = [p for p in (path/'interaction'/'attempts').glob(row['id']+'-*')
               if p.name == Path(row['directory']).name]
    require(len(matches) == 1, 'missing or ambiguous case attempt')
    def checked(k):
        require(k == 'research/'+Path(k).name, 'unexpected receipt path')
        data = (matches[0]/k).read_bytes()
        require(hashlib.sha256(data).hexdigest() == blobs[k], 'receipt digest mismatch')
        return json.loads(data.decode('utf-8-sig'))
    return checked


def scaled_copy_cases(obs, tab):
    expected = {'normal-control': 'WXYZOFFSCREEN', 'double-width': 'WXYZ',
                'upper-half-reverse': 'WXYZ', 'lower-half-spaces': 'W'}
    counts = {}
    for channel, names in [('messages', set(expected)), ('system', {'double-width'} if tab else set())]:
        records = obs.get('scaled_copy_'+channel, [])
        require(len(records)==len(names) and {r['case'] for r in records}==names,
                'missing or duplicate scaled-copy case: '+channel)
        for r in records:
            name = r['case']
            columns = [list(range(36 if name=='normal-control' else 72, 80)), [0,1,2]]
            require(r['highlight']==columns and r['copied']==expected[name]+'\r\nEND'
                    and bytes.fromhex(r['raw_input'])==b'\x1b[0n'*2 and r['passed'] is True,
                    'scaled-copy highlight, clipboard or application input differs: '+channel+'/'+name)
        counts[channel] = len(records)
    return counts


def selection_cursor_case(path,row,identity):
    case=row['id']; tab='-profile-font-' not in case
    renderer={'gdi':1,'directx':3}[case.rsplit('-',1)[1]]
    channel='research/'+('tabs-' if tab else '')+'selection-observed.json'
    obs=record_reader(path,row)(channel)
    require(obs['completed'] and obs['executable_sha256']==identity['executable_sha256']
            and obs['active_renderer']==renderer and obs['tab_host']==tab
            and obs['requested_font']==(identity['font'] if tab else None),'wrong selection window, font or image')
    expected={'cup-inside':True,'tab-across':True,'cht-across':True,'cbt-across':True,
              'print-left-neighbour':True,'overwrite-selected':False,'wide-from-left':False,
              'combine-on-last-selected':False}
    rows=obs['selection_after_cursor_traffic']
    require(len(rows)==len(expected) and {r['name'] for r in rows}==set(expected),'incomplete cursor selection cases')
    for r in rows:
        keep=expected[r['name']]; normal,marked=r['normal'],r['marked']
        require(len(normal)==len(marked)==5 and len(set(normal))==1 and marked[0]==marked[4]==normal[0]
                and marked[1]==marked[2]==marked[3]!=normal[0] and r['after']==(marked if keep else normal),
                'cursor update highlight disagrees with the surrounding cells: '+r['name'])
        # The native fixture uses rows 7 and 14 (protocol coordinates). Pair
        # each raw press/release at the same point; a swallowed right click or
        # stale clipboard cannot prove a correct invalidation.
        ack=b'\x1b[0n'; wire=bytes.fromhex(r['right_click_wire']); allowed=[ack+ack] if keep else [
            ack+f'\x1b[<2;7;{y}M\x1b[<2;7;{y}m'.encode()+ack for y in (7,14)]
        require(r['passed'] and r['expected_selected'] is keep and wire in allowed
                and r['clipboard_updated'] is keep and r['copied']==('EFG' if keep else None),
                'cursor update clipboard or mouse delivery mismatch: '+r['name'])
    # A discarded press must keep its remaining events local, then release
    # the next click to the child. Verify coordinates and bytes independently.
    discards=obs['discarded_scroll_press']
    starts={'pane-top':(12,6),'pane-bottom':(13,13),'row-top':(12,6),'row-bottom':(13,13),
            'left-lead':(7,9),'left-tail':(8,9),'right-lead':(21,9),'right-tail':(22,9)}
    require(len(discards)==len(starts) and {r['case'] for r in discards}==set(starts),'incomplete discarded presses')
    for r in discards:
        x,y=starts[r['case']];ack=b'\x1b[0n';right=f'\x1b[<2;{x+4};{y+1}M\x1b[<2;{x+4};{y+1}m'.encode()
        require(r['passed'] and r['press']==[x,y] and r['changed']==[] and r['clipboard_changed'] is False
                and r['copied'] is None and bytes.fromhex(r['right_wire'])==ack+right+ack
                and r['next_copy']=='SAFE' and bytes.fromhex(r['next_wire'])==bytes.fromhex(r['gesture_wire'])==2*ack,
                'stale highlight, clipboard or mouse ownership after scroll: '+r['case'])
    return len(rows),len(discards),scaled_copy_cases(obs,tab)


def verify_right_gesture(events, manual_paste):
    # Scope the check to this gesture: clients can have their own startup dialogs
    # and exit chords. Require every down and up through the actual submit key.
    rights = [i for i, event in enumerate(events) if event == ['right', True]]
    require(len(rights) == 1, 'expected one system right click')
    i = rights[0]
    select = [[16, True], ['left', True], ['left', False], [16, False]]
    paste = [[17, True], [16, True], [86, True], [86, False], [16, False], [17, False]]
    submit = [['right', True], ['right', False]] + (paste if manual_paste else []) + [[13, True], [13, False]]
    require(i >= len(select) and events[i-len(select):i+len(submit)] == select+submit,
            'wrong Shift-release, right-click, paste-key or submit sequence')


def agent_right_case(path, row, identity, args):
    option = lambda key: args[args.index(key)+1]
    client, renderer, mode = map(option, ('--client', '--renderer', '--right-click'))
    manual = mode == 'default'
    # Fixed provider strings: q + combining acute is stable even in Claude's
    # normalizing editor; the other clients must preserve decomposed e + acute.
    accent = 'q' if '--stable-unicode' in args else 'e'
    sample = 'NEMOTERM_SELECT 中文 '+accent+'\u0301 \uf120 \U000f0001 END'
    digest = hashlib.sha256(('NEMOTERM_SUBMIT '+sample).encode()).hexdigest()
    name = f'research/{client}-selection-{renderer}-system-right-{mode}-observed.json'
    obs = record_reader(path,row)(name)
    child, sess, right = obs['child'], obs['session'], obs['right_click']
    require(obs['completed'] and obs['global_input'] and obs['client']==client and obs['font']==identity['font']
            and sess['renderer']=={'gdi':0,'directx':2}[renderer] and child['terminal_sha256']==identity['executable_sha256']
            and child['client_sha256']==identity['clients'][client]['sha256'] and child['clipboard_restored']
            and not child['cleanup']['terminated_remaining'], 'wrong client, image, font, renderer or cleanup')
    first, y, last = obs['selection']; paint = obs['highlight']
    require(0<first<=last<sess['cols']-1 and 0<=y<sess['rows'] and last-first+1==paint['cells']==30
            and sample in obs['source_line'] and paint['source']!=paint['selected'] and paint['min_selected_ratio']>=.5
            and len(paint['guard_ratios'])==2 and min(paint['guard_ratios'])>=.9, 'wrong highlight or guard cells')
    require(right['mode']==mode and right['setting_written'] is (not manual) and right['modifiers_released']
            and right['clipboard_before']!=right['clipboard_after'] and obs['copied']==sample
            and right['composer_before_paste_key']==('prefix-only' if manual else 'with-selection')
            and obs['composer_form']=='exact', 'wrong clipboard or composer for right-click policy')
    verify_right_gesture(obs['desktop']['events'], manual)
    http = obs['http_receipt']; tracking = obs['mouse_requests_at_drag']['active']
    tagged = [r for r in child['requests'] if r.get('fixture_prompt_hashes')]
    # OpenCode can forward the first user turn to its title model separately.
    # Keep those requests in the record; only the conversation is a submission.
    titles = [r for r in tagged if client=='opencode' and r['has_opencode_title_instruction']]
    submissions = [r for r in tagged if r not in titles]
    require((client!='opencode' or tracking) and http['selection_received'] and http['selected_text_occurrences']==1
            and not http['images'] and http['path']=={'codex':'/v1/responses','opencode':'/v1/chat/completions','claude':'/v1/messages'}[client]
            and http['fixture_prompt_hashes']==[digest] and submissions==[http],
            'wrong application mouse control or submitted user text')
    return dict(client=client, renderer=renderer, policy=mode, explicit_paste_key=manual,
                app_mouse_reporting=tracking, highlighted_cells=paint['cells'], submitted_text_sha256=digest,
                separate_title_requests=len(titles))


def agent_image_case(path, row, identity, args):
    client = args[args.index('--client')+1]
    obs = record_reader(path,row)(f'research/agent-clipboard-{client}.json')
    ready, system = '--after-client-idle' in args, '--system-input' in args
    require(obs['client']==client and obs['completed'] and not obs['failures']
            and obs['after_client_idle'] is ready and obs['system_input'] is system
            and obs['clipboard_format']=='CF_DIB' and obs['font']==identity['font'],
            'wrong client, phase, gesture path, clipboard, or font')
    cases = obs['cases']
    require([c['binding'] for c in cases]==['ctrl-v','ctrl-shift-v'],'missing or duplicate paste binding')
    checks = {}
    for c in cases:
        require(c['terminal_sha256']==identity['executable_sha256'] and c['client_sha256']==identity['clients'][client]['sha256']
                and not c['errors'] and c['clipboard_restored'] and not c['cleanup']['terminated_remaining'],
                'wrong client/product image or incomplete clipboard cleanup')
        checks[c['binding']] = chat_attachment(c['requests'],client,c['binding'])
    return dict(timing='after-client-idle' if ready else 'first-visible-marker', system_keys=system, bindings=checks)


def agent_grid_case(path,row,identity):
    client,renderer=row['id'].removeprefix('agent-grid-').rsplit('-',1)
    client_order=client.endswith('-visual-order');client=client.removesuffix('-visual-order')
    nested=client.endswith('-shell');client=client.removesuffix('-shell')
    actual={'gdi':1,'directx':3}[renderer]
    keys=[k for k in row['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]
    require(len(keys)==1,'missing or ambiguous agent observation')
    obs=record_reader(path,row)(keys[0]);sess=obs['session'];child=obs['child'];trace=obs['frontend_trace']
    if nested:
        pair=child['shell_processes']
        require(obs.get('writer_order_hints')=={'NEMO_SHELL_BEFORE:דהו':False,'AגְבאZ':True,'NEMO_SHELL_AFTER:דהו':False},'wrong owner for a marked span')
        require(pair['output_code_page']==65001 and pair['parent_image'].lower()=='pwsh' and pair['child_image'].lower()=='claude' and pair['parent']!=pair['child'],'missing native shell/client process pair')
    require(obs['client']==client and obs['completed'] and obs['global_input'] and obs['font']==identity['font']
            and child['terminal_sha256']==identity['executable_sha256'] and child['client_sha256']==identity['clients'][client]['sha256']
            and child['cleanup']['terminated_remaining'] is False and (sess['cols'],sess['rows'])==(160,48)
            and sess['renderer']+1==actual,'agent identity, renderer, grid, or cleanup mismatch')
    wide=obs['wide_system_copy'];left,right=wide['columns'];paint=obs['wide_highlight']
    require(wide['copied']==wide['text']=='中文' and right-left==3 and wide['down']==left+1
            and wide['up']==right-1 and paint['cells']==4 and paint['source']!=paint['selected']
            and paint['min_selected_ratio']>=.5 and min(paint['guard_ratios'])>=.9,
            'incomplete wide-cell system drag, highlight, or clipboard result')
    witness=obs['bidi_system_copy'];paint=obs['bidi_highlight'];left,right=witness['columns']
    require(witness['copied']==witness['expected_copy']=='A\u05d2\u05b0' and right==left+1
            and 0<=witness['row']<sess['rows'] and obs['client_visual_order']==client_order and witness['provider_layout_matches']
            and witness['actual_digests']==witness['reference_digests'] and len(set(witness['reference_digests']))==3
            and paint['cells']==2 and paint['source']!=paint['selected'] and paint['min_selected_ratio']>=.5
            and min(paint['guard_ratios'])>=.9,'missing bidi glyph identity, physical highlight, or original clipboard text')
    modal=obs['close_cancel'];http=obs['http_receipt']
    require(modal['button_id']==2 and modal['dialog']!=sess['window'] and modal['owner_disabled']
            and modal['capture']==modal['button'] and modal['button_state'] & 4 and modal['foreground']==sess['window']
            and modal['focus']==sess['hwnd'] and modal['clipboard_intact'] and modal['typed_prefix']=='NEMOTERM_SUBMIT '
            and http['selection_received'] and http['selected_text_occurrences']==1
            and http['fixture_prompt_hashes']==[hashlib.sha256((modal['typed_prefix']+obs['copied']).encode()).hexdigest()],
            'missing native Cancel, terminal focus, physical typing, or exact submitted clipboard text')
    partial=obs['bidi_roundtrip'];drag=partial['bidi_system_copy'];paint=partial['bidi_highlight']
    expected=hashlib.sha256(('NEMOTERM_GLYPH_SUBMIT '+witness['expected_copy']).encode()).hexdigest()
    require(partial['bitmap_sentinel'] and drag['provider_layout_matches'] and drag['start']==drag['end']+1
            and drag['copied']==drag['expected_copy']==witness['copied'] and paint['min_selected_ratio']>=.5
            and min(paint['guard_ratios'])>=.9 and partial['receipt']['glyph_prompt_hashes']==[expected]
            and [r for r in child['requests'] if r.get('glyph_prompt_hashes')]==[partial['receipt']]
            and partial['receipt']['path']==http['path'],'missing reverse-drag glyph round trip to the real client')
    samples=trace['samples'];stages=obs['frontend_samples']
    require(not trace['errors'] and len(samples)>=2 and all(a['seconds']<b['seconds'] for a,b in zip(samples,samples[1:]))
            and [s['phase'] for s in stages]==['startup','reply','copy','composer','submitted'],'incomplete agent workload samples')
    peaks={k:max(v[k] for v in samples+stages) for k in ('private_ws','total_ws','private_commit')}
    require(private_ws_passes(actual,peaks['private_ws']) is True,'agent frontend exceeded its private working-set limit')
    return peaks


def memory_case(path, row, renderer, executable):
    blobs = row['evidence']
    keys = [k for k in blobs if k.startswith('research/') and k.endswith('-memory.json')]
    require(len(keys) == 1, 'missing or ambiguous memory record')
    key, = keys
    meta_key = key[:-len('-memory.json')] + '-observed.json'
    checked=record_reader(path,row)
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
    case_args = {c['id']:c['args'] for c in all_cases}
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
                    if group=='agents' and case.startswith('agent-image-'):
                        out['image_paste'] = agent_image_case(path,row,identity,case_args[case])
                    if group=='agents' and '--right-click' in case_args[case]:
                        out['right_click'] = agent_right_case(path,row,identity,case_args[case])
                    if group=='agents-grid':out['frontend_peak_bytes']=agent_grid_case(path,row,identity)
                    if group=='selection' and case.startswith('selection-'):
                        (out['verified_cursor_updates'], out['verified_discarded_presses'],
                         out['verified_scaled_copy']) = selection_cursor_case(path,row,identity)
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
