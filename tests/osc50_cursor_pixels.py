"""Compare visible OSC 50 cursor shapes against independently painted DECSCUSR controls."""
import argparse
import hashlib
import os
from pathlib import Path

from native_test_utils import c, w, u, root, terminal_host, wait_for, write_snapshot, capture_result
from owned_window_focus import focus_owned_window
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI, OSC, ST = '\x1b[', '\x1b]', '\x1b\\'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('renderer', choices=('gdi', 'directx'))
    renderer = parser.parse_args().renderer
    assert os.environ['RUNNER_ENVIRONMENT'] == 'github-hosted'
    font = os.environ['NEMOTERM_TEST_FONT']
    assert font == 'SarasaTermSC Nerd Light'
    name = 'font-ops-cursor-' + renderer
    out = root/'research'/name
    out.mkdir(exist_ok=False)
    record = dict(renderer=renderer, font=font, cases={}, errors=[], completed=False,
                  executable_sha256=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest())
    number = {'gdi': 1, 'directx': 3}[renderer]

    def exercise(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        assert u.GetPropW(hwnd, 'NemotermRenderer') == number
        owner = w.DWORD(); assert u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        focus_owned_window(terminal_host(hwnd), owner.value, record=record.setdefault('focus', {}))
        cam = PresentedWindowCapture(owner.value, hwnd, directx=number == 3)
        try:
            cam.wait_for_initial_geometry()
            area = w.RECT(); assert u.GetClientRect(hwnd, c.byref(area))
            width, height = area.right, area.bottom
            cw, ch = (width-2)//80, (height-2)//24
            assert cw*80+2 == width and ch*24+2 == height
            record.update(cell=[cw, ch], cell_origin=[1+3*cw, 1+2*ch], actual_renderer=number)
            setup = CSI+'0m'+OSC+'11;#000000'+ST+OSC+'12;#ff0000'+ST+CSI+'2J'+CSI+'?25h'
            query = '\x1bP$q q'+ST
            refs = {}
            # Deliberately start the OSC pass on a different shape to ensure that
            # an ignored command cannot pass by leaving the last control visible.
            for method, order in [('control', (2, 1, 0)), ('osc50', (1, 0, 2))]:
                for digit in order:
                    style = (2, 6, 4)[digit]  # independently specified steady block, beam, underline
                    label = f'{method}-{digit}'; stamp = (19, 77+len(record['cases']), 167)
                    cmd = CSI+f'{style} q' if method == 'control' else OSC+f'50;CursorShape={digit}'+ST
                    mark = CSI+'H'+CSI+('48;2;%d;%d;%dm' % stamp)+' '+CSI+'0m'+CSI+'3;4H'
                    raw = phase(label, setup+mark+cmd+query, None)
                    def read_frame():
                        bmp = cam.capture()[54:]
                        i = (2*width+2)*4
                        if tuple(bmp[i:i+3][::-1]) == stamp: return bmp
                    pixels = wait_for(read_frame)
                    capture_result(width, height, pixels, name+'/'+label+'.png')
                    x0, y0 = record['cell_origin']; rgb = bytearray(); red = set()
                    for y in range(ch):
                        for x in range(cw):
                            i = ((y0+y)*width+x0+x)*4; color = pixels[i:i+3][::-1]
                            rgb.extend(color)
                            if color == b'\xff\x00\x00': red.add((x,y))
                    box = ([min(x for x,y in red), min(y for x,y in red),
                            max(x for x,y in red)+1, max(y for x,y in red)+1] if red else None)
                    digest = hashlib.sha256(rgb).hexdigest()
                    record['cases'][label] = dict(reply=raw.hex(), expected_style=style,
                                                       cell_sha256=digest, red_pixels=len(red), red_box=box)
                    if raw != f'\x1bP1$r{style} q{ST}'.encode(): record['errors'].append(label+': reply')
                    if method == 'control':
                        refs[digit] = digest
                        dx, dy = (box[2]-box[0],box[3]-box[1]) if box else (0,0)
                        valid = (dx >= cw//2 and dy >= ch//2,
                                 0 < dx < cw//2 and dy >= ch//2,
                                 dx >= cw//2 and 0 < dy < ch//2)
                        if not valid[digit]: record['errors'].append(label+': reference geometry')
                    elif digest != refs[digit]: record['errors'].append(label+': presented cell')
            assert len(set(refs.values())) == 3 and not record['errors'], record['errors']
            record['completed'] = True
        finally:
            cam.close(); record['capture'] = cam.record
            write_snapshot(out/'frames.json', record)
    run(name, (), exercise=exercise, barrier=(CSI+'5n',b'\x1b[0n'), font=font,
        profile=dict(NemoTabs=0, NemoRenderer=number-1, WarnOnClose=0, TrueColour=1, NemoAllowSetFont=0),
        source_reference='Alacritty vte 0.15.0 OSC 50 shape; independent DECSCUSR red-window pixels')


if __name__ == '__main__': main()
