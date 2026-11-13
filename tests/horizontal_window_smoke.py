"""Exact cursor/cell replies and raster movement through an owned native window."""
from horizontal_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, time

CSI, DCS, ST = '\x1b[', '\x1bP', '\x1b\\'
FRAME = '\x1bc'+CSI+'?25l'+CSI+'1;2HHORIZONTAL EDITING'+CSI+'12;2HOutside the scrolling region'
RASTER = DCS+'0;1q"1;1;36;18#1;2;100;0;0!36~-#2;2;0;100;0!36~-#3;2;0;0;100!36~'+ST


def exercise(hwnd, phase, current):
    evidence = {}

    def pixels(name, sequence):
        phase(name, sequence, '')
        time.sleep(.08)
        value = capture(hwnd, return_pixels=True)
        evidence[name] = hashlib.sha256(value).hexdigest()
        return value

    right = pixels('right-baseline', FRAME+CSI+'4;7H'+RASTER+CSI+'8;7H中文 e\u0301')
    original = pixels('original-image-and-wide-text', FRAME+CSI+'4;5H'+RASTER+CSI+'8;5H中文 e\u0301')
    assert original != right
    moved = pixels('shift-right', CSI+'?69h'+CSI+'2;30s'+CSI+'3;10r'+CSI+'4;5H'+CSI+'2 A')
    assert moved == right, 'image or full character payload failed to move right'
    moved = pixels('shift-left', CSI+'2 @')
    assert moved == original, 'inverse shift changed pixels'
    moved = pixels('insert-columns', CSI+'4;2H'+CSI+"2'}")
    assert moved == right
    moved = pixels('delete-columns', CSI+"2'~")
    assert moved == original
    moved = pixels('back-index-twice', '\x1b6\x1b6')
    assert moved == right
    moved = pixels('forward-index-twice', CSI+'4;30H\x1b9\x1b9')
    assert moved == original
    for i in range(40):
        pixels(f'repeat-{i}', CSI+'4;5H'+CSI+'2 A'+CSI+'2 @')
    assert capture(hwnd, return_pixels=True) == original
    evidence['inverse_repetitions'] = 40
    outside = pixels('outside-row-is-noop', CSI+'1;5H'+CSI+'99 A'+CSI+'99 @')
    assert outside == original
    blank = pixels('blank-region', FRAME)
    pixels('prepare-erase', FRAME+CSI+'4;5H'+RASTER+CSI+'8;5H中文 e\u0301')
    erased = pixels('full-width-erases-raster', CSI+'?69h'+CSI+'2;30s'+CSI+'3;10r'+CSI+'4;5H'+CSI+'2147483647 A')
    assert erased == blank
    capture(hwnd, 'horizontal-window.png')
    return evidence


run('horizontal', CASES, exercise=exercise,
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(NemoAllowChecksum=1, WarnOnClose=0))
