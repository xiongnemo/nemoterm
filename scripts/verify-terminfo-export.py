"""Compare compiled C table observations with the original libtinfo capture.

This reads files only. Executing the C probe belongs to the hosted workflow.
Absent keys and present empty strings remain different values.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--probe-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.observations, 'rt') as source:
        upstream = json.load(source)
    caps, terminals = [], {}
    with args.probe_output.open(encoding='ascii') as source:
        for line_number, line in enumerate(source, 1):
            record = line.rstrip('\n').split('\t')
            kind = record[0]
            if kind == 'C' and len(record) == 2:
                caps.append(bytes.fromhex(record[1]).decode('ascii'))
            elif kind == 'N' and len(record) == 2:
                name = bytes.fromhex(record[1]).decode('ascii')
                if name in terminals:
                    raise ValueError('Duplicate terminal: ' + name)
                terminals[name] = {}
            elif kind == 'V' and len(record) == 4:
                name, cap = (bytes.fromhex(v).decode('ascii') for v in record[1:3])
                if name not in terminals or cap in terminals[name]:
                    raise ValueError('Unexpected/duplicate key: ' + name + '/' + cap)
                terminals[name][cap] = bytes.fromhex(record[3]).hex()
            else:
                raise ValueError('Malformed compiled record at line ' + str(line_number))
    if caps != upstream['capabilities']:
        raise ValueError('Compiled capability names/order differ')
    expected = upstream['terminals']
    if set(terminals) != set(expected):
        raise ValueError('Compiled terminal aliases differ')
    for name, values in terminals.items():
        if values != expected[name]:
            differences = sorted(k for k in values.keys() | expected[name].keys()
                                 if values.get(k) != expected[name].get(k))
            raise ValueError('Compiled key strings differ: ' + name + ': ' + ', '.join(differences))
    present = sum(len(v) for v in terminals.values())
    result = dict(completed=True, terminals=len(terminals), capabilities=len(caps),
                  compared_slots=len(terminals)*len(caps), present_values=present,
                  absent_values=len(terminals)*len(caps)-present,
                  empty_values=sum(value == '' for values in terminals.values() for value in values.values()),
                  observations_sha256=digest(args.observations),
                  compiled_records_sha256=digest(args.probe_output))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
