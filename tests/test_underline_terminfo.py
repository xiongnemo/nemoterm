"""Interpret actual XTGETTCAP replies with ncurses, not a custom evaluator.

Run on Linux/WSL with --exe <test_tcap>, or --wire-file <native query JSON>.
This is a test-only dependency; the shipped terminal links no curses library.
"""
import argparse
import curses
import hashlib
import json
from pathlib import Path
import subprocess

from underline_capabilities import PROGRAMS, cases, decode_reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--exe', type=Path)
    source.add_argument('--wire-file', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = dict(completed=False, checks=[], ncurses_version=list(curses.ncurses_version))
    try:
        if args.exe:
            evidence['executable_sha256'] = hashlib.sha256(args.exe.read_bytes()).hexdigest()
            result = subprocess.run([str(args.exe.resolve()), '--dump-programs'],
                                    capture_output=True, timeout=30)
            evidence['stderr'] = result.stderr.decode('utf-8')
            evidence['process_exit_code'] = result.returncode
            result.check_returncode()
            replies = dict(line.split('\t') for line in result.stdout.decode('ascii').splitlines())
        else:
            raw = args.wire_file.read_bytes()
            observed = json.loads(raw)
            assert observed['completed'], 'Native query fixture did not complete'
            evidence['native_evidence_sha256'] = hashlib.sha256(raw).hexdigest()
            evidence['executable_sha256'] = observed['executable_sha256']
            replies = {name: observed['tcap-program-'+name]['reply'] for name in PROGRAMS}
        assert set(replies) == set(PROGRAMS)
        evidence['wire_replies'] = replies
        programs = {name: decode_reply(name, bytes.fromhex(wire)) for name, wire in replies.items()}
        curses.setupterm(term='xterm-256color')
        for name, parameter, expected, _ in cases(full=True):
            expanded = curses.tparm(programs[name], parameter)
            assert expanded == expected, (name, parameter, expanded, expected)
            evidence['checks'].append(dict(name=name, parameter=parameter, expanded_hex=expanded.hex()))
        evidence['completed'] = True
        print(f"ncurses expanded {len(evidence['checks'])} actual capability values correctly")
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
