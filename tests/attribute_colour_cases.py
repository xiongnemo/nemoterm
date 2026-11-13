"""OSC 5/6 cases, with reset semantics checked against pinned XTerm(412)."""
CSI, OSC, ST = '\x1b[', '\x1b]', '\x1b\\'
COLORS = ('112233', '445566', '778899', 'aabbcc', 'ddeeff')


def command(op, payload='', end=ST):
    return OSC+str(op)+(';' + payload if payload else '')+end


def reply(op, index, rgb, end=ST):
    parts = [rgb[n:n+2]*2 for n in (0, 2, 4)]
    return OSC+f'{op};{index};rgb:'+('/'.join(parts))+end


def query(op=5):
    return command(op, ';'.join(f'{i if op == 5 else i+256};?' for i in range(5)))


def replies(colors=COLORS, op=5):
    return ''.join(reply(op, i if op == 5 else i+256, color) for i, color in enumerate(colors))


SET = command(5, ';'.join(f'{i};#{color}' for i, color in enumerate(COLORS)))
DEFAULTS = ('ffffff',)*5
CASES = []
for i, color in enumerate(COLORS):
    for op in (4, 5):
        for end in (ST, '\x07'):
            number = i+256 if op == 4 else i
            sequence = command(op, f'{number};#{color};{number};?', end)
            CASES.append((f'set-query-{op}-{number}-'+('st' if end == ST else 'bel'),
                          sequence, reply(op, number, color, end)))
CASES += [
    ('aliases', SET+query(4)+query(), replies(op=4)+replies()),
    ('reset-special-all', SET+command(105)+query(), replies(DEFAULTS)),
    ('reset-indexed-all', SET+command(104)+query(), replies(DEFAULTS)),
    ('reset-one-special', SET+command(105, '2')+query(),
     replies(COLORS[:2]+('ffffff',)+COLORS[3:])),
    ('reset-alias', SET+command(104, '256;260')+query(),
     replies(('ffffff',)+COLORS[1:4]+('ffffff',))),
    ('ordinary-reset-preserves-special', SET+command(104, '0;1;255')+query(), replies()),
    ('invalid-special-index', SET+command(5, '5;red')+query(), replies()),
    ('private-cursor-index-is-not-special', SET+command(4, '261;red')+query(), replies()),
    ('invalid-specification', SET+command(5, '0;#gggggg')+query(), replies()),
    ('overflow-index', SET+command(5, '42949672960;red')+query(), replies()),
    ('negative-index', SET+command(5, '-1;red')+query(), replies()),
    ('incomplete-pair', SET+command(5, '0')+query(), replies()),
    ('mode-does-not-set-colour', SET+command(6, '0;1;1;1;2;1;3;1;4;1')+
     command(106, '0;0;1;0;2;0;3;0;4;0')+query(), replies()),
    ('stack-restores-colours', SET+CSI+'1#P'+command(5, '0;red;1;blue')+
     CSI+'1#Q'+query(), replies()),
    ('stack-restores-defaults', command(105)+CSI+'1#P'+SET+CSI+'1#Q'+query(), replies(DEFAULTS)),
]
for name, control in [('ris', '\x1bc'), ('decstr', CSI+'!p')]:
    CASES.append(('reset-'+name, SET+control+query(), replies(DEFAULTS)))
for name, control in [('alternate', CSI+'?1049h'+CSI+'?1049l'), ('sgr', CSI+'0m')]:
    CASES.append(('retain-'+name, SET+control+query(), replies()))
