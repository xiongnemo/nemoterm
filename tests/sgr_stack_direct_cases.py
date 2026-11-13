"""Nemoterm modern-underline extensions, separate from unchanged XTerm replies."""
CSI = '\x1b['
RESET = CSI+'64;1"p'+(CSI+'#}')*64+'\x1bc'
SAMPLE = CSI+'HA'+CSI+'1;1;1;1#|'
CASES = []
for style in (2, 3):
    for selector in ('', '4', '4;21'):
        expected = f'0;4:{style}'+(';21' if selector == '4' else '')
        CASES.append((f'modern-{style}-{selector or "all"}',
            RESET+CSI+f'4:{style}m'+CSI+selector+'#{'+CSI+'0;21m'+CSI+'#}'+SAMPLE,
            CSI+expected+'m'))

for name, body, reply in (
    ('all-restores-underline-rgb',
     CSI+'4:3;58:2::12:34:56m'+CSI+'#{'+CSI+'0;58:5:7m'+CSI+'#}'+SAMPLE,
     '0;4:3;58:2::12:34:56'),
    ('selective-preserves-current-underline-color',
     CSI+'4:3;58:2::12:34:56m'+CSI+'4#{'+CSI+'0;58:5:7m'+CSI+'#}'+SAMPLE,
     '0;4:3;58:5:7'),
    ('pop-double-reveals-curly',
     CSI+'4:3m'+CSI+'21#{'+CSI+'21m'+CSI+'#}'+SAMPLE, '0;4:3'),
    ('common-double-independent-of-single',
     CSI+'4;21mA'+CSI+'0;21mB'+CSI+'1;1;1;2#|', '0;21'),
    ('modern-style-mismatch',
     CSI+'4:3;58:5:7mA'+CSI+'4:5mB'+CSI+'1;1;1;2#|', '0;58:5:7'),
    ('modern-color-mismatch',
     CSI+'4:3;58:5:7mA'+CSI+'58:5:8mB'+CSI+'1;1;1;2#|', '0;4:3'),
    ('modern-uniform',
     CSI+'4:5;58:2::12:34:56mAB'+CSI+'1;1;1;2#|', '0;4:5;58:2::12:34:56'),
    ('legacy-and-modern-current-state',
     CSI+'4:3;21m'+'\x1bP$qm\x1b\\', None),
):
    CASES.append((name, RESET+body,
                  CSI+reply+'m' if reply is not None else '\x1bP1$r0;4:3;21m\x1b\\'))
