"""Project key identities and unchanged bytes from the retained private XTerm."""
from pathlib import Path
import argparse,hashlib,json,tarfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
args=parser.parse_args()
archive=root/'testdata/upstream/extended-key-resources-reference.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='a59ba35da8865c0fcd3698f2290afe8b63aadefa87ff77d05d676fa2bccf6b7e'
with tarfile.open(archive) as bundle:
    data=json.load(bundle.extractfile('xterm.json'));identity=json.load(bundle.extractfile('IDENTITY.json'))
assert data['completed'] and data['version']=='XTerm(412)' and len(data['cases'])==107
assert identity['source_commit']=='5c75ead9a75d4b2e666ca06fa94503b5766ed93f'
assert identity['executable_sha256']==data['executable_sha256']
special={0xff08:(8,8,0x0e),0xff09:(9,9,0x0f),0xfe20:(0xe120,9,0x0f),
         0xff0d:(13,13,0x1c),0xff1b:(27,27,1),0xff13:(19,19,0x45),
         0xff14:(20,145,0x46)}
keypad={0xff8d:(13,0x11c),0xff95:(36,0x47),0xff96:(37,0x4b),0xff97:(38,0x48),
        0xff98:(39,0x4d),0xff99:(40,0x50),0xff9a:(33,0x49),0xff9b:(34,0x51),
        0xff9c:(35,0x4f),0xff9d:(12,0x4c),0xff9e:(45,0x52),0xff9f:(46,0x53),
        0xffaa:(106,0x37),0xffab:(107,0x4e),0xffac:(108,0x7e),0xffad:(109,0x4a),
        0xffae:(110,0x53),0xffaf:(111,0x135)}
for number,scan in enumerate((0x52,0x4f,0x50,0x51,0x4b,0x4c,0x4d,0x47,0x48,0x49)):
    keypad[0xffb0+number]=(96+number,scan)
modifiers={0xffe1:(160,0x2a),0xffe2:(161,0x36),0xffe3:(162,0x1d),0xffe4:(163,0x11d),
           0xffe5:(20,0x3a),0xffe7:(164,0x38),0xffe8:(165,0x138),
           0xffe9:(164,0x38),0xffea:(165,0x138),0xffeb:(91,0x15b),0xffec:(92,0x15c),
           0xff7f:(144,0x145)}
def event(action):
    symbol=action['keysym'];state=action['state_before']
    assert state & ~(1|2|4|8|16|64)==0,state
    mods=(1 if state&1 else 0)|(2 if state&8 else 0)|(4 if state&4 else 0)|(8 if state&64 else 0)
    if symbol in special:
        resource=7;point,vk,scan=special[symbol]
    elif symbol in modifiers:
        resource=6;point=symbol-0x1d00;vk,scan=modifiers[symbol]
    elif 0xff80<=symbol<=0xffbd:
        resource=3;point=symbol-0x1d00;vk,scan=keypad.get(symbol,(0,0))
    elif symbol in (0xff61,0xff67,0xff6a,0xff6b):
        resource=2;point=symbol-0x1d00;vk=scan=0
    else:raise AssertionError(hex(symbol))
    return dict(resource=resource,codepoint=point,mods=mods,down=bool(action['action'][2]),
                vk=vk,scan=scan,keysym=symbol,state_before=state,requested_key=action['action'][1])
records=[];differences=[]
for name,case in data['cases'].items():
    assert case['completed'] and case['exit_code']==0
    for index,step in enumerate(case['steps']):
        before,after,tail=bytes.fromhex(step['wire_with_barriers_hex']).split(b'\x1b[0n')
        assert not tail and (before+after).hex()==step['reply_hex']
        record=dict(name=name,index=index,reset=index==0,sequence_hex=step['sequence_hex'],
                    reply_hex=step['reply_hex'],before_reply_hex=before.hex(),key_reply_hex=after.hex(),
                    events=[event(a) for a in step['actions_observed']])
        if name.startswith('state-') and name.endswith('-all'):
            differences.append(record);continue
        # These observations exercise the legacy fallback rather than the new
        # extended encoder. Their exact bytes remain available for native tests.
        legacy=bool(after) and (name.startswith('control-') or name.startswith('level-') or
                               (name.startswith('classification-') and name.endswith('resource7')))
        record['core_comparable']=not legacy
        record['windows_comparable']=not legacy and all(e['vk'] for e in record['events'])
        reserved=any(e['down'] and ((e['vk']==45 and e['mods'] in (1,4,6)) or
                                   (e['vk'] in (33,34) and e['mods'] in (1,3))) for e in record['events'])
        record['native_comparable']=record['windows_comparable'] and not reserved
        record['native_exclusion']=('Legacy translation observation' if legacy else
            'No unambiguous standard Windows virtual-key mapping in this fixture' if not record['windows_comparable'] else
            'Existing local clipboard or scroll binding' if reserved else '')
        records.append(record)
assert len(records)==309 and len(differences)==3
def literal(value):
    raw=value.encode() if isinstance(value,str) else value
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,92) else f'\\{b:03o}' for b in raw)+'"'
header='/* Generated from retained XTerm key identities and replies. Do not edit. */\n'
header+='struct extended_key_event { unsigned resource, codepoint, mods, vk, scan, state; bool down; };\n'
header+='struct extended_key_reference { const char *name, *sequence, *reply, *before; bool reset, core, windows; unsigned count; struct extended_key_event events[8]; };\n'
header+='static const struct extended_key_reference extended_keys_reference[] = {\n'
for r in records:
    assert len(r['events'])<=8
    fields=[literal(r['name']),literal(bytes.fromhex(r['sequence_hex'])),literal(bytes.fromhex(r['reply_hex'])),
            literal(bytes.fromhex(r['before_reply_hex'])),str(r['reset']).lower(),
            str(r['core_comparable']).lower(),str(r['windows_comparable']).lower(),str(len(r['events']))]
    events=['{'+', '.join([str(e[k]) for k in ('resource','codepoint','mods','vk','scan','state_before')]+
                           [str(e['down']).lower()])+'}' for e in r['events']]
    header+='    {'+', '.join(fields)+', {'+(', '.join(events) if events else '{0}')+'}},\n'
header+='};\n'
counts={k:sum(r[k] for r in records) for k in ('core_comparable','windows_comparable','native_comparable')}
document=json.dumps(dict(reference_source=identity['source_commit'],counts=counts,cases=records,
    policy_difference='Three reset-all observations differ from the documented all-resource reset contract.',
    observed_policy_differences=differences),indent=2)+'\n'
for path,value in [(root/'tests/extended_keys_reference.h',header),(root/'tests/extended_keys_reference.json',document)]:
    if args.check:assert path.read_text(encoding='utf-8')==value,path
    else:path.write_text(value,encoding='utf-8')
print('Verified' if args.check else 'Generated',json.dumps(counts),'plus three separate reset-policy observations')
