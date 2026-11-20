"""Capture pinned XTerm ReGIS replies and pixels on a hosted private display.

This observes upstream behavior; it does not test or claim Nemoterm support.
Whole and bytewise transports use identical input and independent XTerm
processes. Original replies, images, process exits and failures are retained.
"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
import traceback

from PIL import Image
from xterm_locator_oracle import Display, read, write

E = b'\x1b'
C = E + b'['
ST = E + b'\\'
MARKER = C + b'0n'


def hosted_only():
    if (sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise SystemExit('Reference execution requires a GitHub-hosted Linux runner')


def regis(body, mode=0):
    return E + b'P' + str(mode).encode() + b'p' + body.encode('ascii') + ST


def cases():
    out = {}

    def add(name, *steps):
        assert name not in out
        out[name] = [wire.hex() for wire in steps]

    from shared_bank_start_cases import bank_starts
    for tag,wires in bank_starts().items():
        add('bank-start-'+tag, *(wire.encode('ascii') for wire in wires))

    add('control-text', C+b'6n', b'CONTROL'+C+b'6n', C+b'2J'+C+b'H'+C+b'6n')
    add('control-capability', C+b'c'+C+b'?3;1;0S')
    add('control-position', regis('P[10,20]R(P)', 1), regis('P[+5,-3]R(P)'))
    add('control-line-erase', regis('S(E)', 1),
        regis('W(I3)P[20,20]V[100,20]R(P)'), regis('S(E)'))
    for mode in (0, 1, 2, 3, 4):
        add(f'mode-{mode}', regis('P[30,40]R(P)', 1), regis('R(P)', mode))
        add(f'command-resume-{mode}', regis('P[30,40]', 1),
            regis('[50,60]R(P)', mode))
    for name, body in {
        'absolute': 'P[20,30]V[130,30][130,100][20,100][20,30]',
        'relative': 'P[20,30]V[+80,+0][+0,+60][-80,+0][+0,-60]',
        'pixel-vectors': 'P[40,50]W(M5)V0011223344556677',
        'stack': 'P[20,30](B)[80,90]R(P)P(E)R(P)',
        'circle': 'P[80,60]C[110,60]',
        'arc': 'P[80,60]C(A180)[110,60]',
        'fill': 'F(P[20,20]V[120,20][70,100][20,20])',
        'pattern': 'W(P01010101)P[20,20]V[140,20][140,100][20,100]',
        'write-overlay': 'W(V)P[20,40]V[140,40]',
        'write-replace': 'W(R)P[20,40]V[140,40]',
        'write-complement': 'W(C)P[20,40]V[140,40]P[50,40]V[100,40]',
        'write-erase': 'P[20,40]V[140,40]W(E)P[50,40]V[100,40]',
        'address-range': 'S(A[0,0][319,239])P[40,60]V[260,180]',
        'address-offset': 'S(A[20,20][179,139])P[40,40]V[140,100]',
        'palette-rgb': 'S(M3(R100G0B0))P[20,20]V[140,100]',
        'palette-hls': 'S(M3(H120L50S100))P[20,20]V[140,100]',
        'text-no-font': 'P[20,60]T"ABC"',
    }.items():
        add(name, regis('S(E)W(I3)'+body+'R(P)', 1))
    add('page-roundtrip', regis('S(E)W(I3)P[20,20]V[120,20]', 1),
        regis('P(P1)S(P1)(E)P[20,80]V[120,80]R(P)'),
        regis('S(P0)R(P)'), regis('S(P1)R(P)'))
    add('hidden-page', regis('S(E)W(I3)', 1),
        regis('P(P1)P[20,40]V[120,40]R(P)'), regis('S(P1)R(P)'))
    add('invalid-page', regis('S(E)W(I3)P[20,20]V[120,20]', 1),
        regis('P(P8)S(P8)R(P)'), regis('P(P-1)S(P-1)R(P)'))
    for name, reset in [('ris', E+b'c'), ('decstr', C+b'!p'),
                        ('alternate', C+b'?1049h'),
                        ('alternate-roundtrip', C+b'?1049h'+C+b'?1049l')]:
        add('lifetime-'+name, regis('S(E)W(I3)P[30,40]V[100,40]R(P)', 1),
            reset+C+b'?25l'+regis('R(P)'))
    add('alternate-page-ownership', regis('S(E)W(I3)P[20,20]V[120,20]', 1),
        C+b'?1049h'+regis('W(I2)P[20,80]V[120,80]R(P)'),
        C+b'?1049l'+regis('R(P)'), C+b'?1049h'+regis('R(P)'),
        C+b'?1049l'+regis('R(P)'))
    # Separate a bare screen switch from a following ReGIS query. The old
    # combined sequence cannot show which operation made saved pixels visible.
    for mode in (47, 1047, 1049):
        prefix=C+b'?'+str(mode).encode(); enter=prefix+b'h'; leave=prefix+b'l'
        add(f'alt-graphic-switch-{mode}',
            regis('S(E)W(I3)P[20,20]V[120,20]',1), enter,
            C+b'2;1H'+b'ALT'+regis('W(I2)P[20,80]V[120,80]R(P)'),
            leave, enter, regis('R(P)'), enter, C+b'2J', regis('R(P)'), leave)
    # Write away from the graphic, then enter again while ALT still has content.
    # A plain leave/re-enter would not discriminate clear-on-entry from clear-on-exit.
    for mode in (1047,1049):
        prefix=C+b'?'+str(mode).encode(); enter=prefix+b'h'; leave=prefix+b'l'
        add(f'nonempty-alt-repeat-{mode}', C+b'1;35HM1X', enter,
            C+b'1;35HA2Y'+regis('S(E)W(I2)P[20,80]V[120,80]',1),
            enter, leave, leave, enter, leave)
    # A text status query and a ReGIS query make different mappings. Split
    # switches, queries and erasures into separate captured frames.
    for queried in (False, True):
        add('alt-remap-'+('graphics' if queried else 'text'),
            regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1), C+b'?1049h',
            regis('S(E)S(M2(R100G0B0))W(I2)P[20,80]V[120,80]R(P)'), C+b'?1049l',
            regis('R(P)') if queried else C+b'6n', C+b'?1049h', regis('R(P)'),
            C+b'2J', regis('R(P)'), C+b'?1049l', regis('R(P)'))
    add('alternate-hidden-page', regis('S(E)W(I3)P(P1)P[20,20]V[120,20]', 1),
        C+b'?1049h'+regis('S(P1)R(P)'), C+b'?1049l'+regis('S(P1)R(P)'))
    for name, operation in [('erase-display', C+b'2J'), ('erase-history', C+b'3J'),
                            ('erase-line', C+b'2;1H'+C+b'2K'),
                            ('scroll-up', C+b'3S'), ('scroll-down', C+b'3T'),
                            ('newline-scroll', C+b'12;1H'+b'\n')]:
        add(name, regis('S(E)W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1),
            operation, regis('R(P)'))
    # Separate text-row motion (white markers outside the 160px graphic) from
    # movement of the ReGIS origin. Capture the presented and exposed states
    # before another ReGIS command has a chance to map a new page.
    for name,operation in [('sd',C+b'2T'),('ri',E+b'M'+E+b'M'),('il',C+b'2L'),('su',C+b'2S')]:
        add('scroll-origin-'+name,
            C+b'3;32HA'+C+b'7;32HB'+C+b'H'+regis(
                'S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]R(P)',1),
            operation+C+b'6n', regis('R(P)'),
            regis('S(M2(R100G0B0))W(I2)P[20,50]V[120,50]R(P)'))
    for private in (False,True):
        colour_mode = C+b'?1070'+(b'h' if private else b'l')
        # A palette-only Sixel changes the shared register without supplying
        # an occluding bitmap. Reverse the direction in the separate scene.
        add('sixel-palette-'+str(private), colour_mode+regis('S(E)W(I3)P[20,20]V[120,20]',1),
            E+b'P0;1q#3;2;100;0;0'+ST, regis('R(P)'))
        add('regis-palette-'+str(private), colour_mode+E+b'P0;1q#3!100~'+ST,
            regis('S(M3(R100G0B0))R(P)',1))
        add('page-palette-'+str(private), colour_mode+regis('S(E)W(I3)P[20,20]V[120,20]',1),
            regis('P(P1)S(P1)(E)S(M3(R100G0B0))P[20,80]V[120,80]'),
            regis('S(P0)R(P)'),regis('S(P1)R(P)'))
        # This upstream build starts shared registers black. Keep the default
        # observations above, and separately define green so palette effects
        # cannot pass invisibly. Put Sixel below the ReGIS page to avoid overlap.
        add('sixel-defined-palette-'+str(private), colour_mode+regis(
            'S(E)S(M3(R20G80B20))W(I3)P[20,20]V[120,20]',1),
            E+b'P0;1q#3;2;100;0;0'+ST,regis('R(P)'))
        add('regis-defined-palette-'+str(private), colour_mode+C+b'11;1H'+
            E+b'P0;1q#3;2;20;80;20!100~'+ST,
            regis('S(M3(R100G0B0))R(P)',1))
        add('page-defined-palette-'+str(private), colour_mode+regis(
            'S(E)S(M3(R20G80B20))W(I3)P[20,20]V[120,20]',1),
            regis('P(P1)S(P1)(E)S(M3(R100G0B0))P[20,80]V[120,80]'),
            regis('S(P0)R(P)'),regis('S(P1)R(P)'))
    add('unknown-report', regis('R(Z)', 1), regis('P[20,30]R(P)'))
    add('cancel-can', E+b'P1pP[70,80]'+b'\x18', regis('P[20,30]R(P)'))
    add('cancel-sub', E+b'P1pP[70,80]'+b'\x1a', regis('P[20,30]R(P)'))
    # A following command terminates the final RGB number before ST. Keep
    # these separate from the historical palette-only end-at-ST controls.
    add('shared-palette-sixel-terminated', C+b'?1070l'+regis(
        'S(E)S(M3(R20G80B20))W(I3)P[20,20]V[120,20]',1),
        E+b'P0;1q#3;2;100;0;0#3'+ST,regis('R(P)'))
    # Read the register through a *new* Sixel below the ReGIS line. An old
    # graphic can remain stale until Expose even when the register changed.
    for prefix, ink in [('empty', b''), ('painted', b'#3!12~')]:
        for end, delimiter in [('st', b''), ('dollar', b'$')]:
            add('shared-register-readback-'+prefix+'-'+end,
                C+b'?1070l'+regis('S(E)S(M3(R20G80B20))W(I3)P[20,20]V[120,20]',1),
                C+b'6;5H'+E+b'P9;1q'+ink+b'#3;2;100;0;0'+delimiter+ST,
                C+b'10;5H'+E+b'P9;1q#3!12~'+ST)
    # Exercise the exact trailing definitions used by the private-image
    # decoder tests. Two registers initially share RGB in the first stream;
    # in the second, register 2 overwrites the left half of register 1.
    for label, prefix in [('identity', b'#1;2;100;0;0!8~#2;2;100;0;0!8~'),
                          ('overwrite', b'#1;2;100;0;0!16~$#2;2;0;0;100!8~')]:
        for end, delimiter in [('st', b''), ('dollar', b'$')]:
            add('private-register-'+label+'-'+end,
                C+b'?1070h'+C+b'2;4H'+E+b'P0;1q'+prefix+b'#1;2;0;100;0'+delimiter+ST,
                C+b'6;4H'+E+b'P0;1q#1;2;0;100;0!16~'+ST)
    # Repeat four within-picture cases in one terminal, exactly as the native
    # fixture does. RIS between pictures is distinct from a fresh process.
    private_reset=(E+b'c'+C+b'?25l'+C+b'?80l'+C+b'?1070h'+C+b'0m'+
                   E+b']11;rgb:0/0/0\x07'+C+b'2J'+C+b'3J'+C+b'H')
    chain=[]
    for payload in (b'#1;2;100;0;0!8~#2;2;100;0;0!8~', b'#1;2;100;0;0!16~$#2;2;0;0;100!8~'):
        for delimiter in (b'',b'$'):
            chain.append(private_reset+C+b'2;4H'+E+b'P0;1q'+payload+b'#1;2;0;100;0'+delimiter+ST)
    add('private-reset-chain',*chain)
    # A new DCS should make its first payload byte observable separately from
    # the colour of the previous graphic. Use two colours deliberately unlike
    # the reference's default register 3 and capture all later reads as well.
    seed=C+b'?1070h'+C+b'2;4H'+E+b'P0;1q#1;2;100;0;0!8~#1;2;0;100;0'
    for name, previous_end, barrier, first in (
            ('pending-selector',b'',b'',b'#2;2;0;0;100!8~'),
            ('ended-selector',b'$',b'',b'#2;2;0;0;100!8~'),
            ('pending-dollar',b'',b'',b'$#2;2;0;0;100!8~'),
            ('pending-repeat',b'',b'',b'!8~#2;2;0;0;100!8~'),
            ('pending-literal',b'',b'',b'~#2;2;0;0;100!8~'),
            ('pending-plain-text',b'',C+b'1;1H'+b'T',b'#2;2;0;0;100!8~'),
            ('pending-mode-toggle',b'',C+b'?1070l'+C+b'?1070h',b'#2;2;0;0;100!8~'),
            ('pending-ris',b'',E+b'c'+C+b'?25l'+C+b'?1070h',b'#2;2;0;0;100!8~')):
        add('sixel-next-dcs-'+name,seed+previous_end+ST,
            barrier+C+b'6;4H'+E+b'P0;1q'+first+ST,
            C+b'9;4H'+E+b'P0;1q#2;2;0;0;100!8~'+ST)
    # New digits can finish the prior picture's last numeric field. Use the
    # same selected register in a later explicit read, independent of the pen.
    for name, private, ending, resume in (
            ('rgb-private', True, b'#2;2;100;0;17',b'100$#2!8~'),
            ('rgb-shared',False,b'#2;2;100;0;17',b'100$#2!8~'),
            ('numeric-pen',True,b'#2;2;100;0;17',b'100!8~#2!8~'),
            ('hls-private',True,b'#2;1;240;50;17',b'100$#2!8~'),
            ('selector-number',True,b'#2',b'1!8~'),
            ('selector-empty',True,b'#2',b'#1;2;0;0;100!8~'),
            ('blank-prefix',True,b'#2;2;100;0;17',b'  \t100$#2!8~'),
            ('value-range',True,b'#2;2;100;0;17',b'101!8~#2!8~')):
        mode=C+b'?1070'+(b'h' if private else b'l')
        add('sixel-number-resume-'+name,mode+C+b'2;4H'+E+b'P0;1q#1;2;100;0;0!8~'+ending+ST,
            C+b'6;4H'+E+b'P0;1q'+resume+ST,
            C+b'9;4H'+E+b'P0;1q#2;2;0;0;100!8~'+ST)
    add('shared-palette-regis-recolour', C+b'?1070l'+E+b'P0;1q#3;2;20;80;20!100~'+ST,
        regis('S(M3(R100G0B0))R(P)',1))
    add('alternate-restore-without-regis',regis(
        'S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1),
        C+b'?1049h'+regis('S(E)S(M3(R100G0B0))W(I3)P[20,40]V[120,40]'),
        C+b'?1049l',regis('R(P)'))
    add('margin-scroll-preservation',regis(
        'S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1),
        C+b'3;12r'+C+b'1S',regis('R(P)'))
    # Preserve both presented and exposed frames for the unmodified upstream
    # before and after clearing saved lines. Only require the initial geometry;
    # the following frames are observations, not the product's expectations.
    history=regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1)
    add('erase-saved-main',history,C+b'3S',C+b'3J',C+b'3T')
    add('erase-saved-from-alt',history,C+b'3S',C+b'?1049h'+regis(
        'S(E)S(M3(R100G0B0))W(I3)P[20,40]V[120,40]',1),C+b'3J',C+b'?1049l',C+b'3T')
    return out


def child(report, control):
    import tty
    tty.setraw(0)
    command_id, data = None, b''
    deadline = time.monotonic() + 30
    write(report, dict(command_id=None, hex=''))
    while time.monotonic() < deadline:
        request = read(control)
        if request.get('stop'):
            return
        if request and request.get('id') != command_id:
            command_id, data = request['id'], b''
            wire = bytes.fromhex(request['hex'])
            width = 1 if request['transport'] == 'bytewise' else len(wire)
            for start in range(0, len(wire), width):
                part = wire[start:start+width]
                while part:
                    part = part[os.write(1, part):]
                if width == 1:
                    time.sleep(.001)
        if select.select([0], [], [], .005)[0]:
            chunk = os.read(0, 65536)
            if not chunk:
                return
            data += chunk
        write(report, dict(command_id=command_id, hex=data.hex()))
    raise TimeoutError('Owned reference child exceeded its 30-second lifetime')


class XImage(c.Structure):
    _fields_ = [(name, c.c_int) for name in ('width', 'height', 'xoffset', 'format')]
    _fields_ += [('data', c.c_void_p)]
    _fields_ += [(name, c.c_int) for name in ('byte_order', 'bitmap_unit',
        'bitmap_bit_order', 'bitmap_pad', 'depth', 'bytes_per_line', 'bits_per_pixel')]
    _fields_ += [(name, c.c_ulong) for name in ('red_mask', 'green_mask', 'blue_mask')]


class Pixels(Display):
    def __init__(self, name):
        super().__init__(name)
        self.x.XGetImage.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int,
            c.c_uint, c.c_uint, c.c_ulong, c.c_int]
        self.x.XGetImage.restype = c.POINTER(XImage)
        self.x.XDestroyImage.argtypes = [c.POINTER(XImage)]
        self.x.XDestroyImage.restype = c.c_int
        self.x.XClearArea.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_int]

    def expose(self):
        self.x.XClearArea(self.d,self.window,0,0,0,0,True)
        self.x.XSync(self.d,False)

    def pixels(self, width, height):
        self.x.XSync(self.d, False)
        native = self.x.XGetImage(self.d, self.window, 0, 0, width, height,
                                 c.c_ulong(-1), 2)
        assert native, 'XGetImage failed'
        try:
            info = native.contents
            layout = dict(depth=info.depth, bits_per_pixel=info.bits_per_pixel,
                byte_order=info.byte_order, stride=info.bytes_per_line,
                masks=[info.red_mask, info.green_mask, info.blue_mask])
            assert (info.depth, info.bits_per_pixel, info.byte_order) == (24,32,0), layout
            assert layout['masks'] == [0xff0000, 0xff00, 0xff], layout
            raw = c.string_at(info.data, info.bytes_per_line*height)
            return Image.frombytes('RGB', (width,height), raw, 'raw', 'BGRX',
                                   info.bytes_per_line, 1), layout
        finally:
            self.x.XDestroyImage(native)

    def capture(self, width, height, destination):
        # The reply barrier precedes capture; two equal captures additionally
        # reject unsettled repainting. Keep all attempts instead of masking it.
        time.sleep(.06)
        previous, attempts, started = None, [], time.monotonic()
        while time.monotonic()-started < 2:
            frame, layout = self.pixels(width,height)
            digest = hashlib.sha256(frame.tobytes()).hexdigest()
            attempts.append(dict(rgb_sha256=digest, seconds=time.monotonic()-started))
            if digest == previous:
                frame.save(destination)
                colours = sorted(frame.getcolors(width*height), reverse=True)
                return dict(file=destination.name, width=width, height=height,
                    rgb_sha256=digest, png_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                    colour_count=len(colours), colours=colours[:16], layout=layout,
                    non_black_pixels=sum(count for count,rgb in colours if rgb != (0,0,0)),
                    attempts=attempts)
            previous = digest
            time.sleep(.03)
        frame.save(destination)
        raise AssertionError(('Unsettled reference pixels', attempts))


def capture_case(executable, display_name, name, wires, transport, base, repaint=False, repaint_at=None):
    folder = base/(name+'-'+transport)
    folder.mkdir()
    report, control = folder/'child.json', folder/'control.json'
    display = Pixels(display_name)
    resources = ['-xrm', 'XTerm*locale:false', '-xrm', 'XTerm*cursorBlink:false',
        '-xrm', 'XTerm*regisScreenSize:160x120', '-xrm', 'XTerm*maxGraphicSize:160x120',
        '-xrm', 'XTerm*decGraphicsID:340', '-xrm', 'XTerm*regisDefaultFont:']
    argv = [str(Path(executable).resolve()), '-geometry', '40x12+10+10',
        '-b','2','-bw','0','+sb','-fn','fixed','-fg','white','-bg','black','-ti','vt520' if name.startswith('text-motion-') else 'vt340',
        *resources, '-e',sys.executable,str(Path(__file__).resolve()),
        '--child',str(report.resolve()),str(control.resolve())]
    result = dict(name=name, transport=transport, completed=False, steps=[], argv=argv,
                  forced_cleanup=False)
    terminal = subprocess.Popen(argv, env=dict(os.environ, DISPLAY=display_name),
        stdout=subprocess.DEVNULL, stderr=(folder/'stderr.log').open('wb'))
    counter = 0

    def command(wire):
        nonlocal counter
        counter += 1
        write(control, dict(id=counter, transport=transport, hex=(wire+C+b'5n').hex()))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            value = read(report)
            data = bytes.fromhex(value.get('hex',''))
            if value.get('command_id') == counter and data.endswith(MARKER):
                assert data.count(MARKER) == 1, data
                time.sleep(.03)
                assert read(report) == value, ('Late reference reply', value, read(report))
                return data
            assert terminal.poll() is None, ('XTerm exited',terminal.returncode)
            time.sleep(.005)
        raise TimeoutError((name, transport, counter, read(report)))

    try:
        deadline = time.monotonic()+8
        while not report.exists() and time.monotonic() < deadline:
            assert terminal.poll() is None, ('XTerm startup exit',terminal.returncode)
            time.sleep(.01)
        assert report.exists(), 'Child readiness report missing'
        geometry = command(C+b'?25l'+C+b'16t')
        match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n', geometry)
        assert match, geometry
        width,height = 40*int(match[2])+4,12*int(match[1])+4
        windows = display.windows()
        candidates = [w for w in windows if (w['width'],w['height']) == (width,height)]
        assert candidates, (width,height,windows)
        display.window = max(candidates,key=lambda w:w['depth'])['window']
        result.update(window_tree=windows, viewport=display.window,
                      cell_pixels=[int(match[2]),int(match[1])])
        result['initial_frame'] = display.capture(width,height,folder/'initial.png')
        for index, hex_wire in enumerate(wires):
            wire = bytes.fromhex(hex_wire)
            response = command(wire)
            frame = display.capture(width,height,folder/f'step-{index:02}.png')
            result['steps'].append(dict(sequence_hex=hex_wire,
                reply_hex=response[:-len(MARKER)].hex(),
                wire_with_barrier_hex=(wire+C+b'5n').hex(),
                reply_with_barrier_hex=response.hex(), frame=frame))
            if repaint or index == repaint_at:
                display.expose()
                refreshed_barrier=command(b'')
                refreshed=display.capture(width,height,folder/f'step-{index:02}-exposed.png')
                result['steps'][-1].update(repaint=refreshed,
                    repaint_barrier_hex=refreshed_barrier.hex(),
                    repaint_changed=frame['rgb_sha256']!=refreshed['rgb_sha256'])
            write(folder/'observed.json', result)
        result['capture_completed'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        write(control, dict(stop=True))
        try:
            terminal.wait(timeout=3)
        except subprocess.TimeoutExpired:
            result['forced_cleanup'] = True
            terminal.terminate()
            try:
                terminal.wait(timeout=3)
            except subprocess.TimeoutExpired:
                terminal.kill()
                terminal.wait(timeout=3)
        result['exit_code'] = terminal.returncode
        display.close()
        result['completed'] = (result.get('capture_completed',False)
            and not result['forced_cleanup'] and terminal.returncode == 0)
        write(folder/'observed.json',result)
    return result


def verify_controls(observations):
    failures = []
    for transport in ('whole','bytewise'):
        def replies(name):
            return [bytes.fromhex(step['reply_hex'])
                    for step in observations[name][transport]['steps']]
        try:
            assert replies('control-text') == [C+b'1;1R',C+b'1;8R',C+b'1;1R']
            assert replies('control-position') == [b'[10,20]\r',b'[15,17]\r']
            cap = replies('control-capability')[0]
            da = re.match(rb'\x1b\[\?([0-9;]+)c',cap)
            assert da and b'3' in da[1].split(b';'), cap
            frames = [s['frame'] for s in observations['control-line-erase'][transport]['steps']]
            assert frames[0]['rgb_sha256'] == frames[2]['rgb_sha256']
            assert frames[0]['rgb_sha256'] != frames[1]['rgb_sha256']
            assert frames[1]['non_black_pixels'] > frames[0]['non_black_pixels']+40
            text = [s['frame'] for s in observations['control-text'][transport]['steps']]
            assert text[0]['rgb_sha256'] == text[2]['rgb_sha256'] != text[1]['rgb_sha256']
            for name in ('erase-saved-main','erase-saved-from-alt'):
                assert observations[name][transport]['steps'][0]['frame']['non_black_pixels']==202,name
            for private in (False,True):
                for prefix,pixels in [('sixel',101),('regis',600),('page',101)]:
                    name = prefix+'-defined-palette-'+str(private)
                    visible = [s['frame']['non_black_pixels']
                               for s in observations[name][transport]['steps']]
                    assert visible and all(n==pixels for n in visible), (name,visible)
        except Exception:
            failures.append(dict(transport=transport, error=traceback.format_exc()))
    return failures


def main():
    hosted_only()
    if len(sys.argv)>1 and sys.argv[1] == '--child':
        return child(*map(Path,sys.argv[2:4]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True)
    parser.add_argument('--output',required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--text-motion',action='store_true',help='Fresh process per text edit; checksum text and expose at the last step')
    group.add_argument('--bank-start',action='store_true',help='Only the new shared-register cases and every original control, with both frame types')
    group.add_argument('--first-expose',action='store_true',help='Fresh XTerm for each selected input prefix; expose only at its last step')
    group.add_argument('--repaint',action='store_true',help='Also capture a full Expose after each unchanged step')
    args = parser.parse_args()
    if args.bank_start: args.repaint=True
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    base = output.with_suffix('')
    base.mkdir()
    executable = Path(args.xterm).resolve()
    result = dict(completed=False, scope='Initial ReGIS upstream reference, not product acceptance',
        version=subprocess.check_output([str(executable),'-version'],text=True).strip(),
        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        helper_sha256=hashlib.sha256(Path(__file__).with_name('xterm_locator_oracle.py').read_bytes()).hexdigest(),
        repaint=args.repaint,first_expose=args.first_expose,bank_start=args.bank_start,cases={}, transport_mismatches=[], control_failures=[])
    read_fd,write_fd = os.pipe()
    with (base/'xvfb.log').open('wb') as log:
        xvfb = subprocess.Popen(['Xvfb','-displayfd',str(write_fd),'-screen','0',
            '1024x768x24','-nolisten','tcp'],pass_fds=[write_fd],
            stdout=subprocess.DEVNULL,stderr=log)
    os.close(write_fd)
    try:
        assert select.select([read_fd],[],[],5)[0], 'Xvfb startup timeout'
        display_name = ':'+os.read(read_fd,100).decode().strip()
        assert re.fullmatch(r':\d+',display_name), display_name
        scenes=cases()
        if args.text_motion:
            from regis_text_motion import scenes as text_scenes, verify as verify_motion
            scenes=text_scenes(); result['targets']={k:[k,len(v)-1] for k,v in scenes.items()}
            result['motion_fixture_sha256']=hashlib.sha256(Path(__file__).with_name('regis_text_motion.py').read_bytes()).hexdigest()
        if args.bank_start:
            scenes={k:v for k,v in scenes.items() if k.startswith(('bank-start-','control-','erase-saved-')) or '-defined-palette-' in k}
        if args.first_expose:
            from regis_first_expose import targets, verify_prefixes
            scenes={tag:scenes[name][:last+1] for tag,(name,last) in targets().items()}
            result['targets']=targets()
        for name,wires in scenes.items():
            result['cases'][name] = {}
            for transport in ('whole','bytewise'):
                observed = capture_case(str(executable),display_name,name,wires,transport,base,args.repaint,len(wires)-1 if (args.first_expose or args.text_motion) else None)
                result['cases'][name][transport] = observed
                write(output,result)
                print(name, transport, observed['completed'],
                      [s['reply_hex'] for s in observed['steps']],flush=True)
            whole,bytewise = (result['cases'][name][t] for t in ('whole','bytewise'))
            def comparable(row):
                return [(s['sequence_hex'],s['reply_hex'],s['frame']['rgb_sha256'],
                         s.get('repaint',{}).get('rgb_sha256')) for s in row['steps']]
            if (not whole['completed'] or not bytewise['completed']
                    or comparable(whole) != comparable(bytewise)):
                result['transport_mismatches'].append(name)
        result['control_failures'] = (verify_prefixes(result,base) if args.first_expose
                                      else verify_motion(result['cases']) if args.text_motion else verify_controls(result['cases']))
        result['completed'] = not result['transport_mismatches'] and not result['control_failures']
    finally:
        os.close(read_fd)
        write(output,result)
        xvfb.terminate()
        xvfb.wait(timeout=5)
    assert result['completed'], (result['transport_mismatches'],result['control_failures'])


if __name__ == '__main__':
    main()
