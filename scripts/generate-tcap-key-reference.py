"""Project original hosted XKB events and bytes into a core keyboard fixture."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
archive = root/'research/terminfo-database-evidence.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != '7e3270eadc8063fc85624e67dd3fae0ee26a654e8d82e37374c63199300d0df0':
    raise ValueError('Unexpected startup archive')
with zipfile.ZipFile(archive) as bundle:
    name = next(n for n in bundle.namelist() if n.startswith('44072174561/') and n.endswith('.selected.zip'))
    with zipfile.ZipFile(io.BytesIO(bundle.read(name))) as source:
        data = json.loads(source.read('terminfo-export/startup-keys.json'))
if not data['completed']:
    raise ValueError('Incomplete startup observations')


def literal(value):
    if isinstance(value, str):
        value = value.encode()
    return '"' + ''.join(chr(b) if 32 <= b < 127 and b not in (34, 92)
                         else f'\\{b:03o}' for b in value) + '"'


arrows = {0xff51:'D', 0xff52:'A', 0xff53:'C', 0xff54:'B'}
editing = {0xff50:'SKK_HOME', 0xff55:'SKK_PGUP', 0xff56:'SKK_PGDN',
           0xff57:'SKK_END', 0xff63:'SKK_INSERT', 0xffff:'SKK_DELETE'}


def native_event(action):
    symbol, state = action['keysym'], action['state_before']
    if action['action'][0] != 'key' or state & ~(1|4|8):
        raise ValueError('Unexpected native action or lock state')
    mods = (1 if state & 1 else 0) | (2 if state & 8 else 0) | (4 if state & 4 else 0)
    mapping = {
        0xff51:(37,0x14b), 0xff52:(38,0x148), 0xff53:(39,0x14d), 0xff54:(40,0x150),
        0xff50:(36,0x147), 0xff55:(33,0x149), 0xff56:(34,0x151), 0xff57:(35,0x14f),
        0xff63:(45,0x152), 0xffff:(46,0x153), 0xff8d:(13,0x11c), 0xff9c:(35,0x4f),
        0xffab:(107,0x4e), 0xffb1:(97,0x4f), 0xff08:(8,0x0e), 0xff09:(9,0x0f),
        0xfe20:(9,0x0f), 0xffe1:(160,0x2a), 0xffe3:(162,0x1d),
        0xffe7:(164,0x38), 0xffe9:(164,0x38),
    }
    if symbol in mapping:
        vk, scan = mapping[symbol]
    elif 0xffbe <= symbol <= 0xffe0:
        number = symbol-0xffbe+1
        vk, scan = (0,0) if number == 35 else (111+number, {1:0x3b,5:0x3f,12:0x58,20:0x6b}[number])
    else:
        raise ValueError('Unmapped native symbol: ' + hex(symbol))
    return dict(vk=vk, scan=scan, mods=mods, state_before=state,
                keysym=symbol, down=bool(action['action'][2]))


def normalize_query_hex(reply):
    return re.sub(rb'(\x1bP[01]\+r[^\x1b]*)',
                  lambda m: re.sub(rb'=[0-9a-fA-F]*', lambda h: h[0].lower(), m[0]), reply)


rows = []
records = []
identity_rows = 0
for name, case in data['cases'].items():
    if not case['completed'] or case['exit_code'] != 0:
        raise ValueError('Incomplete startup case')
    for index, step in enumerate(case['steps']):
        events = [a for a in step['actions_observed'] if a['action'][0] == 'key'
                  and a['action'][2] and a['action'][1] not in ('Shift_L', 'Control_L', 'Alt_L')]
        if len(events) > 1:
            raise ValueError('Unexpected multi-key step')
        kind, code, resource, point, mods = 0, '0', 0, 0, 0
        if events:
            symbol, state = events[0]['keysym'], events[0]['state_before']
            if state & ~(1|4|8):
                raise ValueError('Unexpected lock/modifier state')
            mods = (1 if state & 1 else 0) | (2 if state & 8 else 0) | (4 if state & 4 else 0)
            if symbol in arrows:
                kind, code = 1, str(ord(arrows[symbol]))
            elif symbol in editing:
                kind, code = 2, editing[symbol]
            elif 0xffbe <= symbol <= 0xffe0:
                kind, code = 3, str(symbol-0xffbe+1)
            elif 0xff80 <= symbol <= 0xffbd:
                kind, resource, point = 4, 3, symbol-0x1d00
            elif symbol in (0xff08, 0xff09, 0xfe20):
                kind, resource, point = 4, 7, symbol-0xff00 if symbol >= 0xff00 else 0xe120
            else:
                raise ValueError('Unmapped observed symbol: ' + hex(symbol))
        # Only ASCII hex case in a capability response is normalized. Physical
        # input bytes (including ESC, letters and function-key finals) stay exact.
        reply = bytes.fromhex(step['reply_hex'])
        reply = normalize_query_hex(reply)
        # -tn changes XTerm's startup TN as well as its keyboard database.
        # Nemoterm's keyboard-only selector deliberately preserves emulator TN.
        # Retain the complete original reply, but mark this exact prefix for a
        # separate identity-policy assertion. All other bytes compare unchanged.
        identity_bytes = 0
        if reply.startswith(b'\x1bP1+r544e='):
            prefix = b'\x1bP1+r544e=' + case['selected_terminal'].encode().hex().encode() + b';'
            if not reply.startswith(prefix):
                raise ValueError('Unexpected startup identity')
            identity_bytes = len(prefix)
            identity_rows += 1
        values = [literal(name), literal(case['selected_terminal']),
                  literal(bytes.fromhex(step['sequence_hex'])), literal(reply),
                  str(index == 0).lower(), str(kind), code, str(resource), str(point), str(mods),
                  str(identity_bytes)]
        rows.append('    {' + ', '.join(values) + '},')
        before, after, tail = bytes.fromhex(step['wire_with_barriers_hex']).split(b'\x1b[0n')
        if tail or before+after != bytes.fromhex(step['reply_hex']):
            raise ValueError('Unexpected original barrier framing')
        native_events = [native_event(a) for a in step['actions_observed']]
        exclusions = []
        if any(not e['vk'] for e in native_events):
            exclusions.append('F35 has no Win32 virtual-key equivalent; core replay retains it')
        if any(e['down'] and e['vk'] in (33,34) and e['mods'] & 1 for e in native_events):
            exclusions.append('Shift+PageUp/PageDown is the configured local scroll binding')
        records.append(dict(name=name, index=index, terminal=case['selected_terminal'], reset=index==0,
                            sequence_hex=step['sequence_hex'], original_reply_hex=step['reply_hex'],
                            before_reply_hex=normalize_query_hex(before).hex(), key_reply_hex=after.hex(),
                            startup_identity_bytes=identity_bytes, events=native_events,
                            native_comparable=not exclusions, native_exclusion='; '.join(exclusions)))
if len(rows) != 1378:
    raise ValueError('Incomplete startup projection')
header = ('/* Original hosted XTerm bytes and observed XKB identities; no synthesized answers.\n'
          ' * startup_identity_bytes marks the -tn identity prefix for a separate policy check. */\n'
          'static const struct { const char *name, *terminal, *sequence, *reply; bool reset;\n'
          'unsigned kind; int code; unsigned resource, point, mods, startup_identity_bytes; } tcap_key_reference[] = {\n'
          + '\n'.join(rows) + '\n};\n')
document = json.dumps(dict(count=len(records), native_count=sum(r['native_comparable'] for r in records),
    source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    reference_executable_sha256=data['executable_sha256'],
    identity_policy='Keep original XTerm -tn replies; assert Nemoterm TN separately before comparing the unchanged suffix.',
    cases=records), indent=2)+'\n'
for target, value in ((root/'tests/tcap_key_reference.h', header), (root/'tests/tcap_key_reference.json', document)):
    if args.check:
        if target.read_text(encoding='utf-8') != value:
            raise ValueError('Stale startup projection: ' + str(target))
    else:
        target.write_text(value, encoding='utf-8')
print(('Verified' if args.check else 'Generated'), len(rows), 'startup steps;',
      identity_rows, 'startup TN prefixes checked separately;',
      sum(r['native_comparable'] for r in records), 'native steps')
