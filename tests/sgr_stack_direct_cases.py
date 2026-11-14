"""Modern decoration expectations, separate from unchanged XTerm replies.

Overline SGR 53/55 is specified by ECMA-48, fifth edition, section 8.3.117.
Enclosure SGR 51/52/54 is specified in the same section. Selective stack
selectors 51, 52, 53 and 60-64 are Nemoterm extensions for individual aspects.
Ideogram SGR 60-65 follows the same ECMA-48 section.
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

# ECMA-48 60-65 aspects. The selective stack and reply encoding are explicit
# Nemoterm extensions; these are not additions to the captured XTerm oracle.
for value in range(60,65):
    code=str(value)
    for name,body,sgr in (
        ('current',CSI+code+'m','0;'+code),
        ('invalid-subparameter',CSI+code+':1m','0'),
        ('selective-stack',CSI+code+'m'+CSI+code+'#{'+CSI+'65m'+CSI+'#}','0;'+code),
        ('selective-clear',CSI+code+'#{'+CSI+code+'m'+CSI+'#}','0'),
    ):
        CASES.append(('ideogram-'+code+'-'+name,RESET+body+RQ,'\x1bP1$r'+sgr+'m\x1b\\'))
    CASES.append(('ideogram-'+code+'-common',RESET+CSI+code+'mAB'+CSI+'1;1;1;2#|',CSI+'0;'+code+'m'))
    CASES.append(('ideogram-'+code+'-mixed',RESET+CSI+code+'mA'+CSI+'65mB'+CSI+'1;1;1;2#|',CSI+'0m'))
IDEO='60;61;62;63;64'
for name,body,sgr in (
    ('combined',CSI+IDEO+'m','0;'+IDEO),
    ('cancel',CSI+IDEO+'m'+CSI+'65m','0'),
    ('reset',CSI+IDEO+'m'+CSI+'0m','0'),
    ('soft-reset',CSI+IDEO+'m'+CSI+'!p','0'),
    ('hard-reset',CSI+IDEO+'m\x1bc','0'),
    ('invalid-cancel',CSI+IDEO+'m'+CSI+'65:1m','0;'+IDEO),
    ('cursor-restore',CSI+IDEO+'m\x1b7'+CSI+'65m\x1b8','0;'+IDEO),
    ('alternate-restore',CSI+IDEO+'m'+CSI+'?1049h'+CSI+'0m'+CSI+'?1049l','0;'+IDEO),
    ('whole-stack',CSI+IDEO+'m'+CSI+'#{'+CSI+'65m'+CSI+'#}','0;'+IDEO),
    ('stack-across-RIS',CSI+IDEO+'m'+CSI+'#{'+'\x1bc'+CSI+'#}','0;'+IDEO),
    ('other-cancels-independent',CSI+IDEO+'m'+CSI+'24;54;55;59m','0;'+IDEO),
    ('cancel-keeps-other-aspects',CSI+'4:3;21;51;52;53;58;5;7;'+IDEO+'m'+CSI+'65m','0;4:3;21;51;52;53;58;5;7'),
    ('unselected-stack',CSI+'60;53m'+CSI+'53#{'+CSI+'65;55m'+CSI+'#}','0;53'),
    ('cancelled-sequence','\x1b[60\x18','0'),
):
    CASES.append(('ideogram-'+name,RESET+body+RQ,'\x1bP1$r'+sgr+'m\x1b\\'))

for name,body,sgr in (
    ('framed-current',CSI+'51m','0;51'),
    ('encircled-current',CSI+'52m','0;52'),
    ('enclosures-combined',CSI+'51;52m','0;51;52'),
    ('enclosures-cancel-preserves-other-styles',CSI+'4:3;51;52;53m'+CSI+'54m','0;4:3;53'),
    ('enclosures-reset',CSI+'51;52m'+CSI+'0m','0'),
    ('enclosures-soft-reset',CSI+'51;52m'+CSI+'!p','0'),
    ('enclosures-cursor-restore',CSI+'51;52m\x1b7'+CSI+'54m\x1b8','0;51;52'),
    ('enclosures-alternate-restore',CSI+'51;52m'+CSI+'?1049h'+CSI+'0m'+CSI+'?1049l','0;51;52'),
    ('framed-selective-stack',CSI+'51;53m'+CSI+'51#{'+CSI+'54;52;55m'+CSI+'#}','0;51;52'),
    ('encircled-selective-stack',CSI+'52m'+CSI+'52#{'+CSI+'54;51m'+CSI+'#}','0;51;52'),
    ('enclosures-full-stack',CSI+'51;52m'+CSI+'#{'+CSI+'0m'+CSI+'#}','0;51;52'),
    ('enclosures-unselected-stack',CSI+'51;52;53m'+CSI+'53#{'+CSI+'54;55m'+CSI+'#}','0;53'),
    ('enclosures-invalid-set',CSI+'51:1;52:1m','0'),
    ('enclosures-invalid-cancel',CSI+'51;52m'+CSI+'54:1m','0;51;52'),
):
    CASES.append((name,RESET+body+RQ,'\x1bP1$r'+sgr+'m\x1b\\'))
for name,body,sgr in (
    ('enclosures-common',CSI+'51;52mAB'+CSI+'1;1;1;2#|','0;51;52'),
    ('enclosures-mixed',CSI+'51mA'+CSI+'54;52mB'+CSI+'1;1;1;2#|','0'),
    ('enclosures-common-frame',CSI+'51mA'+CSI+'52mB'+CSI+'1;1;1;2#|','0;51'),
):
    CASES.append((name,RESET+body,CSI+sgr+'m'))
