"""Exact Sixel register pixels through the public API of one owned native job."""
import argparse
import struct
import traceback
import uuid
import winreg
from native_test_utils import (root, c, w, u, hashlib, os, subprocess, sys,
    Path, read_snapshot, write_snapshot, wait_for, wait_snapshot)
from owned_job import OwnedJob

sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

ESC, CSI, DCS, ST = '\x1b', '\x1b[', '\x1bP', '\x1b\\'
COLOURS = {'red': b'\x00\x00\xff', 'green': b'\x00\xff\x00',
           'blue': b'\xff\x00\x00', 'vt340-green': b'\x33\xcc\x33',
           'black': b'\0\0\0', 'magenta': b'\xff\0\xff',
           'cyan': b'\xff\xff\0'}  # BMP stores BGR; alpha is not a colour channel.
COLS, ROWS, BORDER = 40, 12, 1
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.PostMessageW.argtypes, u.PostMessageW.restype = [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL


def bitmap(data):
    """Validate the API's bounded, top-down, uncompressed BGRA image."""
    assert len(data) >= 54 and data[:2] == b'BM', 'Expected BMP response'
    size, offset = struct.unpack_from('<I4xI', data, 2)
    dib, width, height, planes, bits, compression = struct.unpack_from('<IiiHHI', data, 14)
    assert size == len(data) and offset == 54 and dib == 40
    assert width > 0 and height < 0 and planes == 1 and bits == 32 and compression == 0
    assert len(data) == 54+width*(-height)*4
    return width, -height, data[54:]


def image(payload, row=2):
    return CSI+f'{row};3H'+DCS+'0;1q"1;1;16;6'+payload+ST


def reset(private=True):
    return (ESC+'c'+CSI+'?25l'+CSI+'?80l'+CSI+'?1070'+('h' if private else 'l')+
            CSI+'0m'+ESC+']11;rgb:0/0/0\x07'+CSI+'2J'+CSI+'3J'+CSI+'H')


def main(background_exercise=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', choices=('gdi', 'opengl', 'directx'), default='gdi')
    args = parser.parse_args()
    suite = 'sixel-background' if background_exercise else 'sixel-palette'
    colour_names = tuple(COLOURS) if background_exercise else ('red', 'green', 'blue')
    requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
    exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
    profile = suite+'-'+uuid.uuid4().hex
    keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    folder = root/'research'/f'{suite}-{args.renderer}-{uuid.uuid4().hex}'
    folder.mkdir(parents=True)
    report, control = folder/'child-report.json', folder/'child-control.json'
    evidence = dict(completed=False, requested_renderer=args.renderer,
        executable=str(exe), executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        folder=str(folder), profile=profile, checks=[], clipboard_access=False,
        global_input=False, capture='public automation API; active renderer BMP')
    evidence['runtime_files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (exe.parent/'OpenConsole.exe', exe.parent/'conpty.dll') if p.exists()}
    profile_created = False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
            profile_created = True
            for name, value in dict(NemoRenderer=requested, WarnOnClose=0, CloseOnExit=1,
                    MouseAutocopy=0, WindowBorder=BORDER, ScrollBar=0,
                    ScrollBarFullScreen=0, FontHeight=12).items():
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        with OwnedJob() as job:
            process, window = None, None
            try:
                command = [str(exe), '-load', profile, '--automation',
                    '--cols', str(COLS), '--rows', str(ROWS), '--font', 'Consolas',
                    '-e', sys.executable, str(root/'tests/mouse_fixture.py'),
                    str(report), str(control), '180']
                evidence['command'] = command
                process = job.spawn(command, env=dict(os.environ,
                    NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                evidence['pid'] = process.pid
                instance = wait_for(lambda: next(iter(api.discover(process.pid)), None), timeout=20)
                assert instance['pid'] == process.pid and len(instance['sessions']) == 1, instance
                endpoint, session = instance['endpoint'], instance['sessions'][0]
                seat, window = session['id'], session['window']
                assert session['active'] and seat and session['hwnd'] and window, session
                for hwnd in (session['hwnd'], window):
                    owner = w.DWORD()
                    assert u.GetWindowThreadProcessId(hwnd, c.byref(owner)) and owner.value == process.pid
                actual = session['renderer']
                evidence.update(endpoint=endpoint, session=session, actual_renderer=actual)
                assert actual in (0, requested), (requested, actual)
                if requested == 1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1':
                    assert actual == 1, 'OpenGL fell back'
                if requested == 2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1':
                    assert actual == 2, 'DirectX fell back'

                def current():
                    value = read_snapshot(report)
                    assert process.poll() is None and not value.get('error'), value
                    return value

                wait_snapshot(current, lambda v: v.get('columns') == COLS and v.get('rows') == ROWS)
                width, height, _ = bitmap(api.request(endpoint, 'image', seat))
                cw, ch = (width-2*BORDER)//COLS, (height-2*BORDER)//ROWS
                assert cw > 0 and ch >= 6 and width == COLS*cw+2*BORDER and height == ROWS*ch+2*BORDER
                evidence.update(image_size=[width, height], cell_pixels=[cw, ch])

                def block(row, colour, left=0, count=16, top=0, height=6):
                    return dict(x=BORDER+2*cw+left, y=BORDER+(row-1)*ch+top,
                                width=count, height=height, colour=colour)

                def phase(name, sequence, regions):
                    serial = len(evidence['checks'])+1
                    record = dict(name=name, sequence=sequence, sequence_hex=sequence.encode().hex(),
                        barrier_sequence_hex=(CSI+'5n').encode().hex(), input_barrier=serial,
                        regions=regions, matched=False)
                    evidence['checks'].append(record)
                    write_snapshot(control, dict(phase=name, sequence=sequence,
                        preserve_mouse=True, input_barrier=serial))
                    value = wait_snapshot(current, lambda v: v.get('phase') == name and
                                          v.get('input_barrier') == serial)
                    record['reply_hex'] = value['hex']
                    assert bytes.fromhex(value['hex']).endswith((CSI+'0n').encode()), value
                    assert [value['columns'], value['rows']] == [COLS, ROWS], value
                    # Later rectangles overwrite earlier ones, so a one-pixel
                    # foreground can be specified over a full background ROI.
                    wanted_pixels = {}
                    for region in regions:
                        for y in range(region['y'], region['y']+region['height']):
                            for x in range(region['x'], region['x']+region['width']):
                                assert 0 <= x < width and 0 <= y < height
                                wanted_pixels[x, y] = region['colour']
                    wanted = {colour: set() for colour in colour_names}
                    for point, colour in wanted_pixels.items():
                        wanted[colour].add(point)
                    record['scope'] = 'exact probe regions' if background_exercise else 'all client RGB probe colours'
                    record['expected_counts'] = {colour: len(points) for colour, points in wanted.items()}
                    last = None

                    def matches():
                        nonlocal last
                        last = api.request(endpoint, 'image', seat)
                        image_width, image_height, pixels = bitmap(last)
                        assert (image_width, image_height) == (width, height)
                        observed = {colour: set() for colour in colour_names}
                        colours = {COLOURS[colour]: colour for colour in colour_names}
                        if background_exercise:
                            for x, y in wanted_pixels:
                                offset = (y*width+x)*4
                                bgr = pixels[offset:offset+3]
                                colour = colours.get(bgr, 'rgb:'+bgr[::-1].hex())
                                observed.setdefault(colour, set()).add((x, y))
                        else:
                            for offset in range(0, len(pixels), 4):
                                colour = colours.get(pixels[offset:offset+3])
                                if colour:
                                    observed[colour].add((offset//4 % width, offset//4 // width))
                        record['observed_counts'] = {colour: len(points) for colour, points in observed.items()}
                        record['differences'] = {colour: dict(
                            missing=sorted(wanted.get(colour, set())-observed.get(colour, set()))[:8],
                            unexpected=sorted(observed.get(colour, set())-wanted.get(colour, set()))[:8])
                            for colour in sorted(wanted.keys() | observed.keys())}
                        return observed == wanted

                    try:
                        wait_for(matches)
                        record['matched'] = True
                    finally:
                        if last is not None:
                            basename = f'{serial:02d}-{name}'
                            (folder/(basename+'.bmp')).write_bytes(last)
                            (folder/(basename+'.png')).write_bytes(api.png_from_bmp(last))
                            record.update(bmp=basename+'.bmp', png=basename+'.png',
                                          bmp_sha256=hashlib.sha256(last).hexdigest())
                        write_snapshot(folder/'checks.json', evidence['checks'])
                    print(name, record['observed_counts'], flush=True)

                if background_exercise:
                    background_exercise(phase, block)
                else:
                    red, green = '#1;2;100;0;0!16~', '#1;2;0;100;0!16~'
                    recolour = '#1;2;100;0;0!8~#1;2;0;100;0!8~'
                    phase('private-same-dcs-before', reset()+image(red), [block(2, 'red')])
                    phase('private-same-dcs-after', reset()+image(recolour), [block(2, 'green')])
                    phase('shared-same-dcs', reset(False)+image(recolour), [block(2, 'green')])
                    phase('private-cross-before', reset()+image(red), [block(2, 'red')])
                    phase('private-cross-after', image(green, 5), [block(2, 'red'), block(5, 'green')])
                    phase('equal-rgb-distinct-registers', reset()+image(
                        '#1;2;100;0;0!8~#2;2;100;0;0!8~#1;2;0;100;0?'),
                        [block(2, 'green', count=8), block(2, 'red', left=8, count=8)])
                    phase('overwrite-register-identity', reset()+image(
                        '#1;2;100;0;0!16~$#2;2;0;0;100!8~#1;2;0;100;0?'),
                        [block(2, 'blue', count=8), block(2, 'green', left=8, count=8)])
                    phase('shared-cross-before', reset(False)+image(red), [block(2, 'red')])
                    phase('shared-cross-after', image(green, 5), [block(2, 'green'), block(5, 'green')])
                    # '?' commits the completed numeric definition; CAN must not
                    # roll it back. Keep the same expectation through ConPTY.
                    phase('shared-cancel', DCS+'0;1q#1;2;0;0;100?\x18', [block(2, 'blue'), block(5, 'blue')])
                    phase('private-cancel', CSI+'?1070h'+DCS+'0;1q#1;2;100;0;0?\x18',
                        [block(2, 'blue'), block(5, 'blue')])
                    phase('private-image-after-mode-toggle', image(green, 8),
                        [block(2, 'blue'), block(5, 'blue'), block(8, 'green')])
                    phase('shared-mode-restored', CSI+'?1070l'+DCS+'0;1q#1;2;100;0;0?'+ST,
                        [block(2, 'red'), block(5, 'red'), block(8, 'green')])
                    phase('soft-reset-retains-images', CSI+'!p'+CSI+'?25l',
                        [block(2, 'red'), block(5, 'red'), block(8, 'green')])
                    phase('shared-after-soft-reset', CSI+'?1070l'+DCS+'0;1q#1;2;0;0;100?\x18',
                        [block(2, 'blue'), block(5, 'blue'), block(8, 'green')])
                    # Do not follow RIS with ED: that could hide a broken RIS
                    # image-lifetime boundary. Only hide its restored cursor.
                    phase('hard-reset-clears-images', ESC+'c'+CSI+'?25l', [])
                final = api.request(endpoint)
                assert final['pid'] == process.pid and len(final['sessions']) == 1
                assert final['sessions'][0]['id'] == seat and final['sessions'][0]['active']
                assert final['sessions'][0]['renderer'] == actual, final
                assert u.PostMessageW(window, 0x10, 0, 0)  # WM_CLOSE, this owned window only.
                assert process.wait(timeout=15) == 0
                assert api.discover(process.pid) == []
                evidence['cleanup'] = job.finish()
                assert not evidence['cleanup']['terminated_remaining'], evidence['cleanup']
                evidence['completed'] = True
            finally:
                evidence['last_snapshot'] = read_snapshot(report)
                if process is not None and process.poll() is None and window:
                    owner = w.DWORD()
                    if u.GetWindowThreadProcessId(window, c.byref(owner)) and owner.value == process.pid:
                        u.PostMessageW(window, 0x10, 0, 0)
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            pass  # Only the private job is terminated below.
                evidence['cleanup'] = job.finish(grace=0)
    except BaseException:
        evidence['error'] = traceback.format_exc()
        raise
    finally:
        try:
            if profile_created:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
            evidence['profile_removed'] = True
        finally:
            write_snapshot(root/'research'/f'{suite}-{args.renderer}-observed.json', evidence)
    print(f'Native {suite} {args.renderer}: {len(evidence["checks"])} exact pixel checks passed', flush=True)


if __name__ == '__main__':
    main()
