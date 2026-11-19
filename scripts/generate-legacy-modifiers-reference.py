"""Project unchanged resource-0 replies and observed XKB identities."""
from pathlib import Path
import argparse,hashlib,json,tarfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
args=parser.parse_args()
archive=root/'testdata/upstream/legacy-modifiers-reference.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='6af81cb1535135c42c75e48a91369dd3bccf2660e18bfb1c654c93c0074f85d3'
with tarfile.open(archive) as bundle:
    data=json.load(bundle.extractfile('xterm.json'));identity=json.load(bundle.extractfile('IDENTITY.json'))
assert data['completed'] and data['version']=='XTerm(412)'
assert identity['source_commit']=='5c75ead9a75d4b2e666ca06fa94503b5766ed93f'
assert identity['executable_sha256']==data['executable_sha256']
assert len(data['cases'])==98 and sum(len(c['steps']) for c in data['cases'].values())==2895
profiles={'default':6,'legacy':8,'vt220':7}
arrows={0xff51:('D',37,0x14b),0xff52:('A',38,0x148),0xff53:('C',39,0x14d),0xff54:('B',40,0x150)}
editing={0xff50:('SKK_HOME',36,0x147),0xff55:('SKK_PGUP',33,0x149),
    0xff56:('SKK_PGDN',34,0x151),0xff57:('SKK_END',35,0x14f),
    0xff63:('SKK_INSERT',45,0x152),0xffff:('SKK_DELETE',46,0x153)}
keypad={0xff8d:(13,0x11c),0xff9c:(35,0x4f),0xffab:(107,0x4e),
    0xffaf:(111,0x135),0xffb1:(97,0x4f)}
modifiers={0xffe1:(160,0x2a),0xffe3:(162,0x1d),0xffe7:(164,0x38),0xffe9:(164,0x38)}

def event(action):
    symbol,state=action['keysym'],action['state_before']
    assert state&~(1|2|4|8|16|64)==0
    mods=(1 if state&1 else 0)|(2 if state&8 else 0)|(4 if state&4 else 0)|(8 if state&64 else 0)
    kind=0;code='0'
    if symbol in arrows:
        resource=1;point=symbol-0x1d00;final,vk,scan=arrows[symbol];kind=1;code=repr(final)
    elif symbol in editing:
        resource=1;point=127 if symbol==0xffff else symbol-0x1d00
        code,vk,scan=editing[symbol];kind=3
    elif 0xffbe<=symbol<=0xffe0:
        resource=2;point=symbol-0x1d00;kind=2;number=symbol-0xffbe+1;code=str(number)
        vk=111+number;scan={1:0x3b,6:0x40,12:0x58,20:0x6b}[number]
    elif symbol in modifiers:
        resource=6;point=symbol-0x1d00;vk,scan=modifiers[symbol]
    elif symbol in keypad:
        resource=3;point=symbol-0x1d00;vk,scan=keypad[symbol]
    elif symbol in (0xff61,0xff67,0xff6a):
        resource=2;point=symbol-0x1d00;vk,scan={0xff61:(44,0x137),0xff67:(93,0x15d),0xff6a:(47,0x163)}[symbol]
    elif symbol in (0xff1b,0xff15):
        resource=7;point=symbol-0xff00;vk,scan=(27,1) if symbol==0xff1b else (44,0x137)
    else:raise AssertionError(hex(symbol))
    return dict(resource=resource,codepoint=point,mods=mods,state_before=state,
        down=bool(action['action'][2]),kind=kind,code=code,vk=vk,scan=scan,keysym=symbol)

records=[];differences=[]
for name,case in data['cases'].items():
    assert case['completed'] and case['exit_code']==0
    for index,step in enumerate(case['steps']):
        before,after,tail=bytes.fromhex(step['wire_with_barriers_hex']).split(b'\x1b[0n')
        assert not tail and (before+after).hex()==step['reply_hex']
        events=[event(a) for a in step['actions_observed']]
        reserved=any(e['down'] and ((e['vk']==45 and (e['mods']&5) in (1,4)) or
            (e['vk'] in (33,34) and (e['mods']&5 in (1,5) or
             (case['profile']!='default' and e['mods']&5==4)))) for e in events)
        record=dict(name=name,index=index,reset=index==0,profile=profiles[case['profile']],
            sequence_hex=step['sequence_hex'],reply_hex=step['reply_hex'],before_reply_hex=before.hex(),
            key_reply_hex=after.hex(),events=events,native_comparable=not reserved,
            native_exclusion='Configured local clipboard or scroll binding' if reserved else '')
        if name.startswith('state-'):
            # All state observations request DECRQSS >0f. XTerm 412 answers
            # with an m suffix (misc.c FMT_FMT_FKEYS), which restores the wrong
            # resource. Keep Nemoterm's existing round-trip-safe f contract.
            # Reset-all and signed disabled replies also retain the established
            # policy. These complete raw observations are never parity claims.
            differences.append(record)
        else: records.append(record)
assert len(records)==2872 and len(differences)==23
def literal(value):
    raw=value.encode() if isinstance(value,str) else value
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,92) else f'\\{b:03o}' for b in raw)+'"'
header='/* Generated from unchanged private XTerm resource-0 observations. */\n'
header+='struct legacy_modifier_event { unsigned resource, codepoint, mods, state, kind; int code; bool down; };\n'
header+='struct legacy_modifier_reference { const char *name, *sequence, *reply; int profile; bool reset; unsigned count; struct legacy_modifier_event events[8]; };\n'
header+='static const struct legacy_modifier_reference legacy_modifiers_reference[] = {\n'
for r in records:
    assert len(r['events'])<=8
    fields=[literal(r['name']),literal(bytes.fromhex(r['sequence_hex'])),literal(bytes.fromhex(r['reply_hex'])),
        str(r['profile']),str(r['reset']).lower(),str(len(r['events']))]
    events=['{'+', '.join([str(e[k]) for k in ('resource','codepoint','mods','state_before','kind')]+
        [e['code'],str(e['down']).lower()])+'}' for e in r['events']]
    header+='    {'+', '.join(fields)+', {'+(', '.join(events) if events else '{0}')+'}},\n'
header+='};\n'
document=json.dumps(dict(reference_source=identity['source_commit'],count=len(records),
    native_count=sum(r['native_comparable'] for r in records),cases=records,
    observed_policy_differences=differences,
    policy_difference='DECRQSS format replies retain f for safe restoration; reset-all resets all resources; disabled replies use restorable 65535.'),indent=2)+'\n'
for path,value in [(root/'tests/legacy_modifiers_reference.h',header),(root/'tests/legacy_modifiers_reference.json',document)]:
    if args.check:assert path.read_text(encoding='utf-8')==value,path
    else:path.write_text(value,encoding='utf-8')
print('Verified' if args.check else 'Generated',len(records),'unchanged steps;',sum(r['native_comparable'] for r in records),'native steps')
