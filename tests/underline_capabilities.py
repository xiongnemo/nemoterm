"""Independent expected terminfo programs and their numeric meaning (test data).

Smulx follows ncurses terminfo.src, revision 7404b376832583182c52722dc09d86b8675db375.
Setulc takes one packed RGB integer, as documented in tmux's usstyle feature.
The programs are interpreted by real ncurses in test_underline_terminfo.py;
this module deliberately contains no terminfo interpreter.
"""

PROGRAMS = {
    'Smulx': b'\x1b[4:%p1%dm',
    'Setulc': b'\x1b[58:2::%p1%{65536}%/%d:%p1%{256}%/%{255}%&%d:%p1%{255}%&%dm',
}
RGB_BOUNDARIES = (0, 1, 255, 256, 65535, 65536, 0x123456, 0x80ff01, 0xffffff)


def cases(full=False):
    for style in range(6):
        sequence = f'\x1b[4:{style}m'.encode()
        report = '' if style == 0 else ';4' if style == 1 else f';4:{style}'
        yield 'Smulx', style, sequence, f'\x1bP1$r0{report}m\x1b\\'.encode()
    colours = set(RGB_BOUNDARIES)
    if full:
        # All byte values in each channel, with nonzero other channels. This
        # checks masks, division boundaries and channel order independently.
        for n in range(256):
            colours.update(((n << 16) | 0x3456, 0x120056 | (n << 8), 0x123400 | n))
    for colour in sorted(colours):
        r, g, b = colour >> 16, (colour >> 8) & 255, colour & 255
        sequence = f'\x1b[58:2::{r}:{g}:{b}m'.encode()
        yield 'Setulc', colour, sequence, f'\x1bP1$r0;58:2::{r}:{g}:{b}m\x1b\\'.encode()


def decode_reply(name, wire):
    prefix = b'\x1bP1+r'+name.encode().hex().encode()+b'='
    # Native captures also contain a final DSR barrier, core dumps do not.
    if wire.endswith(b'\x1b[0n'):
        wire = wire[:-4]
    assert wire.startswith(prefix) and wire.endswith(b'\x1b\\'), (name, wire)
    program = bytes.fromhex(wire[len(prefix):-2].decode('ascii'))
    assert program == PROGRAMS[name], (name, program)
    return program
