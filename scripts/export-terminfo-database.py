"""Export pinned ncurses key data as compact, read-only C tables on Actions.

The terminal database is compiled by upstream tic and read by upstream libtinfo.
No terminal capabilities or escape strings are synthesized from Nemoterm.
"""
import argparse
import ctypes as c
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capability_names(source):
    """Extract XTerm's literal names and extended modifier-name macro groups."""
    text = source.read_text()
    names = set(re.findall(r'DATA\(\s*"[^"]*",\s*"([^"]+)"', text))
    base = None
    for line in text.splitlines():
        definition = re.match(r'#define BASE "([^"]+)"', line)
        group = re.match(r'\s*DGRP\(\s*(\w+),', line)
        if definition:
            base = definition[1]
        if group:
            if base is None:
                raise ValueError('Extended key group without a name prefix')
            names.add(base + group[1])
            names.update(base + group[1] + str(n) for n in range(3, 9))
    # These are identity/numeric queries, not key strings in XTerm's table.
    names.difference_update(('colors', 'RGB', 'name'))
    if not {'kf1', 'kf63', 'kcuu1', 'kUP8', 'kpZRO8', 'kbs', 'kcbt'} <= names:
        raise ValueError('Incomplete pinned XTerm capability table')
    return sorted(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--xtermcap', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        parser.error('Database export requires a GitHub-hosted Linux runner')
    args.output.mkdir(parents=True, exist_ok=False)
    database = args.database.resolve(strict=True)
    os.environ['TERMINFO'] = os.environ['TERMINFO_DIRS'] = str(database)
    names = sorted({p.name for p in database.rglob('*') if p.is_file()})
    if 'xterm-256color' not in names:
        raise ValueError('Default terminal entry is absent')
    caps = capability_names(args.xtermcap)
    library = c.CDLL(str(args.library.resolve(strict=True)))
    library.setupterm.argtypes = [c.c_char_p, c.c_int, c.POINTER(c.c_int)]
    library.setupterm.restype = c.c_int
    library.tigetstr.argtypes = [c.c_char_p]
    library.tigetstr.restype = c.c_void_p
    library.del_curterm.argtypes = [c.c_void_p]
    library.del_curterm.restype = c.c_int
    library.use_extended_names.argtypes = [c.c_int]
    library.use_extended_names.restype = c.c_int
    library.use_extended_names(1)
    current = c.c_void_p.in_dll(library, 'cur_term')
    unavailable, captured = [], {}
    for name in names:
        error = c.c_int()
        status = library.setupterm(name.encode('ascii'), 1, c.byref(error))
        try:
            if status != 0 or error.value != 1:
                unavailable.append(dict(name=name, status=status, error=error.value))
                continue
            values = {}
            for index, cap in enumerate(caps):
                pointer = library.tigetstr(cap.encode('ascii'))
                if pointer not in (None, c.c_void_p(-1).value):
                    values[index] = c.string_at(pointer)
            captured[name] = values
        finally:
            if current.value and library.del_curterm(current.value) != 0:
                raise RuntimeError('Unable to retire the owned database')
    if 'xterm-256color' not in captured:
        raise ValueError('Default database was rejected by libtinfo')

    pool = bytearray(b'\0')
    offsets = {b'': 0}

    def intern(value):
        if value not in offsets:
            offsets[value] = len(pool)
            pool.extend(value + b'\0')
        return offsets[value]

    cap_names = [intern(cap.encode('ascii')) for cap in caps]
    profiles, profile_ids, entries, aliases = [], {}, [], []
    # A zero-initialized terminal uses the default without touching the table.
    for name in ['xterm-256color'] + [n for n in sorted(captured) if n != 'xterm-256color']:
        key = tuple(captured[name].items())
        if key not in profile_ids:
            profile_ids[key] = len(profiles)
            profiles.append((len(entries), len(key)))
            entries.extend((cap, intern(value)) for cap, value in key)
        aliases.append((name, intern(name.encode('ascii')), profile_ids[key]))
    aliases.sort()
    header = ['/* Generated from pinned ncurses/XTerm data; see the accompanying manifest. */',
              '/* ncurses data license: COPYING.ncurses */', '#include <stdint.h>',
              'typedef struct { uint32_t name, profile; } NemoTcapDbName;',
              'typedef struct { uint32_t first, count; } NemoTcapDbProfile;',
              'typedef struct { uint32_t cap, value; } NemoTcapDbValue;',
              'static const unsigned char nemo_tcap_db_bytes[] = {']
    for start in range(0, len(pool), 20):
        header.append('    ' + ','.join(str(v) for v in pool[start:start+20]) + ',')
    header += ['};', 'static const uint32_t nemo_tcap_db_cap_names[] = {',
               '    ' + ','.join(map(str, cap_names)), '};',
               'static const NemoTcapDbName nemo_tcap_db_names[] = {']
    header += [f'    {{{offset},{profile}}},' for _, offset, profile in aliases]
    header += ['};', 'static const NemoTcapDbProfile nemo_tcap_db_profiles[] = {']
    header += [f'    {{{first},{count}}},' for first, count in profiles]
    header += ['};', 'static const NemoTcapDbValue nemo_tcap_db_values[] = {']
    header += [f'    {{{cap},{value}}},' for cap, value in entries]
    header += ['};', '']
    generated = args.output / 'nemo_tcap_database.inc'
    generated.write_text('\n'.join(header))
    raw = dict(capabilities=caps, terminals={name: {caps[k]: v.hex() for k, v in values.items()}
                                           for name, values in captured.items()})
    with gzip.GzipFile(filename=str(args.output/'libtinfo-key-observations.json.gz'),
                       mode='wb', mtime=0) as output:
        output.write((json.dumps(raw, sort_keys=True) + '\n').encode())
    longest = max((len(value), name, caps[cap]) for name, values in captured.items()
                  for cap, value in values.items())
    result = dict(completed=True, fixture_commit=os.environ['GITHUB_SHA'],
        ncurses_commit='789942a72295ac37b53a8a167ba9a016325a9ef1',
        xterm_commit='5c75ead9a75d4b2e666ca06fa94503b5766ed93f',
        source_sha256=digest(args.source), xtermcap_sha256=digest(args.xtermcap),
        library_sha256=digest(args.library), header_sha256=digest(generated),
        compiled_names=len(names), selectable_names=len(aliases),
        unavailable=unavailable, capabilities=len(caps), unique_profiles=len(profiles),
        sparse_values=len(entries), pool_bytes=len(pool),
        maximum_key=dict(bytes=longest[0], terminal=longest[1], capability=longest[2]),
        readonly_bytes=len(pool)+4*len(cap_names)+8*(len(aliases)+len(profiles)+len(entries)),
        default_profile=0, source='Upstream tic database and upstream libtinfo string lookup')
    (args.output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='unavailable'},indent=2))
    print('Library-rejected terminal names:',len(unavailable))


if __name__ == '__main__':
    main()
