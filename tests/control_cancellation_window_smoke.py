"""Replay lossless UTF-8 reference streams through an owned native ConPTY job."""
from ansi_conformance_native_cases import CASES as ANSI, EXCLUDED as ANSI_BINARY
from ansi_conformance_native_cases import REFERENCE_SHA256 as ANSI_SHA
from control_cancellation_native_cases import CASES as CANCEL, EXCLUDED as CANCEL_BINARY
from control_cancellation_native_cases import REFERENCE_SHA256 as CANCEL_SHA
from native_test_utils import capture, hashlib, time
from protocol_oracle_window import run

CSI = '\x1b['
cases = [('ansi-'+name, text, reply) for name, text, reply in ANSI]
cases += [('cancel-'+name, text, reply) for name, text, reply in CANCEL]


def exercise(hwnd, phase, current):
    evidence = dict(ansi_reference_sha256=ANSI_SHA, cancellation_reference_sha256=CANCEL_SHA,
                    native_ansi_cases=len(ANSI), native_cancellation_cases=len(CANCEL),
                    ansi_binary_cases_not_run=ANSI_BINARY, cancellation_binary_cases_not_run=CANCEL_BINARY,
                    pixel_pairs={})
    frame = '\x1b%G\x1bc'+CSI+'65;1"p'+CSI+'?25l'+CSI+'2;2H'

    def pixels(name, text):
        phase(name, text, b'')
        time.sleep(.08)
        result = capture(hwnd, return_pixels=True)
        return result, hashlib.sha256(result).hexdigest()

    for name, expected, actual in (
            ('utf8-sub', 'A\u2426B', 'A'+CSI+'1;\x1aB'),
            ('byte-sub', '\x1b%@A&B', '\x1b%@A\x1b]2;unfinished\x1aB'),
            ('utf8-can', 'AB', 'A\x1bP$qm\x18B')):
        baseline, baseline_sha = pixels(name+'-literal', frame+expected)
        observed, observed_sha = pixels(name+'-control', frame+actual)
        assert observed == baseline, (name, observed_sha, baseline_sha)
        evidence['pixel_pairs'][name] = dict(literal_sha256=baseline_sha, control_sha256=observed_sha)
    return evidence


run('control-cancellation', cases, exercise=exercise,
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(LineCodePage='ISO-8859-1', UTF8Override=0, UTF8linedraw=1,
                 NemoAllowChecksum=1, WarnOnClose=0),
    source_reference='XTerm(412); 413 UTF-8-transportable streams; 84 binary-only cases excluded')
