"""Unicode image cells and virtual parents through native ConPTY and pixels.

The shared controller owns its process/window, uses no global input or
clipboard, retains every input and screenshot, and checks the entire text grid.
This is renderer validation, not an uninjected memory acceptance measurement.
"""
import os
from kitty_image_window_smoke import command, reset, CSI
from sixel_palette_window_smoke import main

PUA = '\U0010eeee'
MARKS = ['\u0305', '\u030d', '\u030e', '\u0310']


def exercise(phase, block):
    cw = (block(2, 'red')['x'] - 1) // 2
    ch = block(3, 'red')['y'] - block(2, 'red')['y']
    fg = CSI + '38;5;42m'
    cup = lambda x, y: CSI + f'{y+1};{x+1}H'

    def cell(row=0, column=0, high=None):
        return PUA + MARKS[row] + MARKS[column] + (MARKS[high] if high is not None else '')

    def text(x=2, y=1):
        return fg + ''.join(cup(x, y+r) + ''.join(cell(r, c) for c in range(4)) for r in range(2))

    def upload(ident=42, placement=7, colour=(255, 0, 0), width=None, height=None):
        width = width or 4*cw
        height = height or 2*ch
        return command(f'a=T,i={ident},p={placement},f=24,s={width},v={height},c=4,r=2,U=1,C=1',
                       bytes(colour)*width*height)

    def tile(colour, x=2, y=1, columns=4, rows=2):
        return block(y+1, colour, left=(x-2)*cw, count=columns*cw, height=rows*ch)

    def check(name, wire, *regions, **kwargs):
        phase(name, wire, [tile('black', 0, 0, 40, 12), *regions], **kwargs)

    clean = reset() + command('a=d,d=R,x=1,y=4294967295') + CSI + 'H'
    check('template-invisible', clean + upload())
    check('explicit-cells', text(), tile('red'))
    check('erase-first-two-cells', cup(2, 1) + CSI + '2X',
          tile('red', 4, 1, 2, 1), tile('red', 2, 2, 4, 1))
    check('overwrite-second-row', cup(2, 2) + ' '*4, tile('red', 4, 1, 2, 1))
    check('ED2-removes-cells', CSI + '2J')
    check('template-survives-ED2', text(), tile('red'))
    check('inferred-row-run', CSI + '2J' + cup(2, 1) + fg + cell() + PUA*3,
          tile('red', 2, 1, 4, 1))
    check('scalar-REP-spacing-base', CSI + '2J' + cup(2, 1) + fg + cell() + CSI + '3b',
          tile('red', 2, 1, 4, 1))
    check('scroll-cells-up', cup(0, 11) + '\n', tile('red', 2, 0, 4, 1))
    check('delete-template-hides-existing-text', command('a=d,d=I,i=42,p=7'))
    check('new-template-reuses-existing-text', upload(), tile('red', 2, 0, 4, 1))
    check('spatial-delete-preserves-cells', command('a=d,d=A'), tile('red', 2, 0, 4, 1))
    check('RIS-removes-cells', '\x1bc' + CSI + '?25l')
    check('template-survives-RIS', text(), tile('red'))
    check('ED3-preserves-visible-text', CSI + '3J', tile('red'))
    check('alternate-hides-main', CSI + '?1049h' + CSI + '?25l' + CSI + 'H')
    check('alternate-independent-template', upload(colour=(0, 255, 0)) + text(), tile('green'))
    check('alternate-restores-main', CSI + '?1049l', tile('red'))

    child = command('a=T,i=43,p=9,f=24,s=1,v=1,c=1,r=1,C=1,P=42,Q=7,H=4,V=0', bytes((0, 0, 255)))
    check('virtual-child-hidden-without-cells', clean + upload() + child)
    check('virtual-child-visible-at-anchor', text(), tile('red'), tile('blue', 6, 1, 1, 1))
    check('earlier-cell-moves-virtual-child', cup(0, 0) + fg + cell(),
          tile('red'), tile('red', 0, 0, 1, 1), tile('blue', 4, 0, 1, 1))
    check('erase-earlier-anchor-restores-child', cup(0, 0) + CSI + 'X',
          tile('red'), tile('blue', 6, 1, 1, 1))
    check('erase-all-anchors-hides-child', cup(2, 1) + CSI + '4X' + cup(2, 2) + CSI + '4X')
    check('hidden-child-is-retained', text(), tile('red'), tile('blue', 6, 1, 1, 1))
    check('virtual-letterbox', clean + upload(colour=(0, 255, 0), width=cw, height=ch) + text(),
          tile('green', 3, 1, 2, 2))
    check('underline-placement-selects-template', clean + upload(placement=7) +
          command('a=p,i=42,p=11,U=1,c=4,r=2,C=1') + CSI + '58;5;11m' + text(), tile('red'))
    check('unknown-template-is-invisible', CSI + '2J' + CSI + '58;5;12m' + text())
    check('high-image-byte', clean + upload(ident=(1 << 24) + 42) + fg + cup(2, 1) + cell(0, 0, 1) + PUA*3,
          tile('red', 2, 1, 4, 1))
    check('unknown-image-is-invisible', clean + fg + cup(2, 1) + cell() + PUA*3)
    check('stable-repaint', upload() + text(), tile('red'), stable_seconds=2)


if __name__ == '__main__':
    main(exercise, suite_name='kitty-unicode',
         font=os.environ.get('NEMOTERM_TEST_FONT', 'Consolas' if os.environ.get('CI') == 'true'
                             else 'SarasaTermSC Nerd Font Light'))
