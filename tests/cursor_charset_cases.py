"""Authored cursor/charset expectations; independent runtime capture is pending."""
ESC, CSI, DCS, ST = '\x1b', '\x1b[', '\x1bP', '\x1b\\'
RESET, QUERY = CSI+'65;1"p'+ESC+'c', CSI+'1$w'
GL = ('\x0f', '\x0e', ESC+'n', ESC+'o')
GR = {1: ESC+'~', 2: ESC+'}', 3: ESC+'|'}


def setup(sets, gl, gr, row=5, col=9):
    return ''.join(ESC+bank+value for bank, value in zip('()*+', sets)) + \
        GL[gl]+GR[gr]+CSI+f'{row};{col}H'


def reply(sets='BBBB', gl=0, gr=2, row=1, col=1, flags='@'):
    return DCS+f'1$u{row};{col};1;@;@;{flags};{gl};{gr};@;{sets}'+ST


CASES = []
for name, save, restore in (
    ('dec', ESC+'7', ESC+'8'),
    ('ansi', CSI+'s', CSI+'u'),
    ('1048', CSI+'?1048h', CSI+'?1048l'),
):
    for gl in range(4):
        for gr in (1, 2, 3):
            CASES.append((f'{name}-gl{gl}-gr{gr}',
                          RESET+setup('0AB0', gl, gr)+save+
                          setup('B0AB', (gl+1)%4, 1+gr%3, 9, 17)+restore+QUERY,
                          reply('0AB0', gl, gr, 5, 9)))

main = setup('0AB0', 2, 1)
alternate = setup('B0AB', 3, 2, 7, 11)
changed = setup('BBBB', 1, 3, 9, 17)
main_reply = reply('0AB0', 2, 1, 5, 9)
alt_reply = reply('B0AB', 3, 2, 7, 11)
CASES += [
    ('restore-before-save', RESET+main+ESC+'8'+QUERY, reply()),
    ('ris-clears-cache', RESET+main+ESC+'7'+ESC+'c'+changed+ESC+'8'+QUERY, reply()),
    ('soft-reset-clears-active-cache', RESET+main+ESC+'7'+CSI+'!p'+changed+ESC+'8'+QUERY,
     reply()),
    ('single-shift-is-not-resurrected',
     RESET+setup('BB0B', 0, 2, 1, 1)+ESC+'N'+ESC+'7q'+changed+ESC+'8'+QUERY,
     reply('BB0B')),
    ('live-single-shift-survives-restore',
     RESET+main+ESC+'7'+changed+ESC+'O'+ESC+'8'+QUERY,
     reply('0AB0', 2, 1, 5, 9, 'D')),
    ('independent-screen-caches',
     RESET+main+ESC+'7'+CSI+'?47h'+alternate+ESC+'7'+changed+ESC+'8'+QUERY+
     CSI+'?47l'+changed+ESC+'8'+QUERY+CSI+'?47h'+ESC+'8'+QUERY+CSI+'?47l',
     alt_reply+main_reply+alt_reply),
    ('1049-restores-main-charsets',
     RESET+main+CSI+'?1049h'+alternate+ESC+'7'+CSI+'?1049l'+QUERY, main_reply),
    ('soft-reset-retains-inactive-cache',
     RESET+main+ESC+'7'+CSI+'?47h'+alternate+ESC+'7'+CSI+'!p'+changed+ESC+'8'+QUERY+
     CSI+'?47l'+ESC+'8'+QUERY, reply()+main_reply),
]
