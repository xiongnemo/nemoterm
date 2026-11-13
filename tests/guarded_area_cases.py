"""Authored SPA/EPA expectations; not yet compared with a running reference."""
ESC, CSI, DCS, ST = '\x1b', '\x1b[', '\x1bP', '\x1b\\'
SPA, EPA = ESC+'V', ESC+'W'
RESET = CSI+'65;1"p'+ESC+'c'
RQSS = DCS+'$q"q'+ST
CASES = []


def add(name, body, cells, protected=(), decsca=0):
    # Individual cell checks avoid losing position information in one sum.
    # Mode 21 includes the protected attribute's weight and undrawn blanks.
    checks, expected = CSI+'21#y', ''
    for index, scalar in enumerate(cells.ljust(8)):
        col = index+1
        checks += CSI+f'{col};1;1;{col};1;{col}*y'
        value = ord(scalar)+(4 if col in protected else 0)
        expected += DCS+f'{col}!~{value:04X}'+ST
    expected += DCS+f'1$r{decsca}"q'+ST
    CASES.append((name, RESET+body+checks+RQSS, expected))


for family, start, end, reset in (
    ('iso', SPA, EPA, ''),
    ('dec', CSI+'1"q', CSI+'0"q', ''),
    ('off', CSI+'1"q', CSI+'0"q', CSI+'!p'),
):
    scene = 'A'+start+'BC'+end+'DEF'+reset+CSI+'1;2H'
    for selective in (False, True):
        keep = family == 'iso' or (family == 'dec' and selective)
        for kind in ('J', 'K'):
            for mode in (0, 1, 2):
                text = (('ABC   ', ' BCDEF', ' BC   ') if keep else
                        ('A     ', '  CDEF', '      '))[mode]
                protection = (2, 3) if keep or mode == 1 else ()
                if not keep and mode == 1: protection = (3,)
                add(f'{family}-'+('selective-' if selective else 'ordinary-')+kind+str(mode),
                    scene+CSI+('?' if selective else '')+str(mode)+kind, text, protection)
    add(f'{family}-ech', scene+CSI+'1;1H'+CSI+'6X',
        ' BC   ' if family == 'iso' else '      ', (2, 3) if family == 'iso' else ())

scene = 'A'+SPA+'BC'+EPA+'DEF'+CSI+'H'
add('iso-selective-rectangle-ignores-iso-family', scene+CSI+'1;1;1;6${', '      ', (2, 3))
add('iso-ordinary-rectangle-clears-protection', scene+CSI+'1;1;1;6$z', '      ')
add('last-dec-family-wins', scene+CSI+'0"q'+CSI+'2K', '      ')
add('last-iso-family-wins', 'A'+CSI+'1"qBC'+CSI+'0"qDEF'+SPA+EPA+CSI+'2K', ' BC   ', (2, 3))
add('epa-does-not-switch-dec-family', 'A'+CSI+'1"qBC'+EPA+'DEF'+CSI+'2K', '      ')
add('sgr-reset-keeps-iso-write-protection', SPA+'A'+CSI+'0mB'+EPA+'C'+CSI+'2K', 'AB ', (1, 2))
add('ordinary-write-overwrites-guarded-cell', SPA+'ABC'+EPA+CSI+'1;2Hz', 'AzC', (1, 3))
add('soft-reset-ends-iso-family', scene+CSI+'!p'+CSI+'2K', '      ')
add('ris-ends-iso-family', SPA+ESC+'cABC'+CSI+'2K', '   ')

for attribute in ('@', 'A'):
    restore = DCS+'1$t1;1;1;@;'+attribute+';@;0;2;@;BBBB'+ST
    add('presentation-retains-iso-'+attribute, scene+restore+CSI+'2K', ' BC   ', (2, 3))
    add('rectangle-after-presentation-'+attribute, scene+restore+CSI+'1;1;1;6${',
        '      ', (2, 3))

# An ISO guard flag alone must not be reported as DECSCA. Cursor saves restore
# the write flag, while the currently selected protection family stays live.
add('iso-decrqss-is-zero', SPA+'A', 'A', (1,))
add('cursor-restores-flag-in-current-dec-family',
    SPA+'A'+ESC+'7'+EPA+CSI+'0"q'+ESC+'8B', 'AB', (1, 2), decsca=1)
add('cursor-restore-does-not-revive-reset-family',
    SPA+'A'+ESC+'7'+CSI+'!p'+ESC+'8B'+CSI+'2K', '  ')

for mode, position in ((2, CSI+'H'), (0, CSI+'H'), (1, CSI+'24;80H')):
    # Retiring an empty family leaves the write flag intact. A newly written
    # protected cell is then erasable until SPA/DECSCA selects a family again.
    add(f'empty-full-ed-{mode}-retires-family',
        SPA+position+CSI+str(mode)+'J'+CSI+'H'+'A'+CSI+'2K', ' ')

for control in ('K', '1K', '2K', 'X', '2J'):
    # The whole first row is protected, so EL1/EL2 preserve pending wrap.
    # EL0/ECH cancel it through ClearRight; ED2 erases unprotected lower rows.
    body = SPA+'Q'*80+CSI+control+CSI+'6nR'+CSI+'6n'
    wrap = control in ('1K', '2K')
    expected = CSI+'1;80R'+(CSI+'2;2R' if wrap else CSI+'1;80R')
    CASES.append(('pending-wrap-'+control, RESET+body, expected))
