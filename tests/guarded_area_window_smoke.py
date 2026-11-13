"""Prepared GDI/ConPTY guarded-area checks; no clipboard or global input."""
from guarded_area_cases import CASES, ESC, CSI, DCS, ST, SPA, EPA, RESET
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, time, wait_for, os

FRAME = RESET+CSI+'?25l'
TEXT = 'KEEP中文 e\u0301'
IMAGE = CSI+'4;3H'+DCS+'0;1q#1;2;100;0;0!48~'+ST


def scene(protected=False):
    begin, end = (SPA, EPA) if protected else ('', '')
    return (FRAME+CSI+'2;3H'+begin+TEXT+end+
            CSI+'4;3H'+begin+' '*24+end+IMAGE)


def exercise(hwnd, phase, current):
    evidence = dict(pixel_checks=[], clipboard_access=False)

    def pixels(name, sequence):
        phase(name, sequence, '')
        time.sleep(.08)
        value = capture(hwnd, return_pixels=True)
        evidence['pixel_checks'].append(dict(name=name, sha256=hashlib.sha256(value).hexdigest()))
        return value

    blank = pixels('blank', FRAME)
    text_only = pixels('text-baseline', FRAME+CSI+'2;3H'+TEXT)
    expected = pixels('text-and-sixel-baseline', scene())
    assert expected != text_only and text_only != blank
    before = pixels('iso-guarded-with-extra-output', scene(True)+CSI+'6;3HDROP')
    assert before != expected
    actual = pixels('ordinary-ed-preserves-guarded-content', CSI+'2J')
    assert actual == expected, 'ordinary ED changed ISO guarded text or Sixel pixels'
    actual = pixels('ordinary-rectangle-clears-guarded-sixel', CSI+'4;3;4;26$z')
    assert actual == text_only
    actual = pixels('dec-selective-rectangle-ignores-iso-family', CSI+'2;1;2;40${')
    assert actual == blank

    before = pixels('before-synchronized-erase', scene(True)+CSI+'6;3HDROP')
    frozen = pixels('synchronized-erase-held', CSI+'?2026h'+CSI+'2J')
    assert frozen == before
    phase('synchronized-erase-released', CSI+'?2026l', '')
    wait_for(lambda: capture(hwnd, return_pixels=True) == expected)
    actual = pixels('soft-reset-then-ordinary-erase', CSI+'!p'+CSI+'?25l'+CSI+'2J')
    assert actual == blank

    # State transitions do not allocate per-character/per-guard storage.
    phase('bounded-guard-transitions', (SPA+EPA+CSI+'0"q')*1000, '')
    pixels('gallery', scene(True))
    capture(hwnd, 'guarded-area-window.png')
    evidence['state_transition_cycles'] = 1000
    return evidence


run('guarded-area', (), extra_cases=CASES, exercise=exercise,
    source_reference='Authored cases independently matched XTerm(412); research/protocol-reference-validation.json',
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(NemoRenderer=0, NemoAllowChecksum=1, MouseAutocopy=0, WarnOnClose=0),
    font=os.environ.get('NEMOTERM_TEST_FONT',
        'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
