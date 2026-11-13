"""Modern underline/overline expectations, separate from unchanged XTerm replies.

Overline SGR 53/55 is specified by ECMA-48, fifth edition, section 8.3.117.
Its selective SGR-stack selector 53 is a Nemoterm extension.
"""
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

RQ = '\x1bP$qm\x1b\\'
for name,body,sgr in (
    ('overline-current', CSI+'53m', '0;53'),
    ('overline-cancel', CSI+'53m'+CSI+'55m', '0'),
    ('overline-reset', CSI+'53m'+CSI+'0m', '0'),
    ('overline-soft-reset', CSI+'53m'+CSI+'!p', '0'),
    ('overline-cursor-restore', CSI+'53m\x1b7'+CSI+'55m\x1b8', '0;53'),
    ('overline-alternate-restore', CSI+'53m'+CSI+'?1049h'+CSI+'0m'+CSI+'?1049l', '0;53'),
    ('overline-with-underlines', CSI+'53;4:3;21;58:2::12:34:56m', '0;4:3;21;53;58:2::12:34:56'),
    ('overline-underline-reset', CSI+'53;4:3;21;58:2::12:34:56m'+CSI+'24;59m', '0;53'),
    ('overline-selective-stack', CSI+'53;4:3m'+CSI+'53#{'+CSI+'55;4:5m'+CSI+'#}', '0;4:5;53'),
    ('overline-whole-stack', CSI+'53m'+CSI+'#{'+CSI+'0m'+CSI+'#}', '0;53'),
    ('overline-unselected-stack', CSI+'53;4:3m'+CSI+'4#{'+CSI+'55;24m'+CSI+'#}', '0;4:3'),
    ('overline-invalid-subparameter-set', CSI+'53:1m', '0'),
    ('overline-invalid-subparameter-reset', CSI+'53m'+CSI+'55:1m', '0;53'),
):
    CASES.append((name,RESET+body+RQ,'\x1bP1$r'+sgr+'m\x1b\\'))
for name,body,sgr in (
    ('overline-common',CSI+'53mAB'+CSI+'1;1;1;2#|','0;53'),
    ('overline-mixed',CSI+'53mA'+CSI+'55mB'+CSI+'1;1;1;2#|','0'),
):
    CASES.append((name,RESET+body,CSI+sgr+'m'))
