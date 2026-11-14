"""Implicit register 3 and declared register-0 fill via owned API BMP captures.

These RGB defaults are NemoTerm's VT340 palette; the register identity is also
used by pinned XTerm VT330, whose default register 3 is white instead of green.
"""
from sixel_palette_window_smoke import main, reset, ESC, CSI, DCS, ST


def exercise(phase, block):
    def image(payload, p2=0, row=2, raster=True):
        return CSI+f'{row};3H'+DCS+f'9;{p2}q'+('"1;1;8;6' if raster else '')+payload+ST

    def setup(private=True):
        # Contrasting text background and foreground must not select Sixel's
        # register-0 background or register-3 default set-pixel colour.
        return reset(private)+ESC+']11;#ff00ff\x07'+CSI+'2J'+CSI+'31m'

    def rect(row, colour, **kwargs):
        return block(row, colour, count=kwargs.pop('count', 8), **kwargs)

    def dot(row, colour='vt340-green', **kwargs):
        return rect(row, colour, count=1, height=1, **kwargs)

    def scene(*overlays, text='magenta'):
        return [rect(row, text) for row in (2, 5, 8)]+list(overlays)

    for p2 in (0, 1, 2):
        phase(f'p2-{p2}-implicit-colours', setup()+image('@', p2),
              scene(rect(2, 'magenta' if p2 == 1 else 'black'), dot(2)))
    phase('implicit-register3-redefinition', setup()+image('@#3;2;100;0;0?'),
          scene(rect(2, 'black'), dot(2, 'red')))
    phase('opaque-register0-redefinition', setup()+image('@#0;2;0;0;100?'),
          scene(rect(2, 'blue'), dot(2)))
    phase('opaque-independent-of-OSC11', ESC+']11;#00ffff\x07',
          scene(rect(2, 'blue'), dot(2), text='cyan'))
    phase('transparent-register0-redefinition', setup()+image('@#0;2;0;0;100?', 1), scene(dot(2)))
    phase('transparent-follows-OSC11', ESC+']11;#00ffff\x07', scene(dot(2), text='cyan'))

    phase('shared-and-private-background-before', setup(False)+image('@')+
          CSI+'?1070h'+image('@', row=5), scene(rect(2, 'black'), dot(2), rect(5, 'black'), dot(5)))
    phase('shared-background-CAN', CSI+'?1070l'+DCS+'9;1q#0;2;0;0;100#3;2;100;0;0?\x18',
          scene(rect(2, 'blue'), dot(2, 'red'), rect(5, 'black'), dot(5)))
    phase('soft-reset-retains-background-ownership', CSI+'!p'+CSI+'?25l',
          scene(rect(2, 'blue'), dot(2, 'red'), rect(5, 'black'), dot(5)))
    phase('background-redefinition-after-soft-reset', DCS+'9;1q#0;2;100;0;0#3;2;0;0;100?\x18',
          scene(rect(2, 'red'), dot(2, 'blue'), rect(5, 'black'), dot(5)))
    phase('RIS-clears-background-images', ESC+'c'+CSI+'?25l', scene())
    phase('shared-defaults-after-RIS', CSI+'?1070l'+image('@'), scene(rect(2, 'black'), dot(2)))

    sparse = [dot(2), dot(2, left=2, top=1)]
    phase('no-raster-sparse-opaque', setup()+image('@?A', raster=False), scene(*sparse))
    phase('no-raster-holes-follow-OSC11', ESC+']11;#00ffff\x07', scene(*sparse, text='cyan'))
    small = [rect(2, 'black', count=2, height=2), *sparse]
    phase('set-pixels-outside-declared-fill', setup()+image('"1;1;2;2@?A', raster=False), scene(*small))
    phase('undeclared-holes-follow-OSC11', ESC+']11;#00ffff\x07', scene(*small, text='cyan'))
    underlay = image('#1;2;100;0;0!8~', 1)
    phase('raster-only-underlay-before', setup()+underlay, scene(rect(2, 'red')))
    phase('raster-only-does-not-cover', image(''), scene(rect(2, 'red')))
    phase('first-zero-sixel-activates-fill', image('?'), scene(rect(2, 'black')))
    phase('transparent-zero-sixel-retains-underlay', setup()+underlay+image('?', 1), scene(rect(2, 'red')))


if __name__ == '__main__':
    main(background_exercise=exercise)
