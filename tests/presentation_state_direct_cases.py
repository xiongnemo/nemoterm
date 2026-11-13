"""Explicit PuTTY extensions and presentation-state recovery differences."""
CSI, DCS, ST = '\x1b[', '\x1bP', '\x1b\\'
RESET, QUERY = CSI+'65;1"p\x1bc', CSI+'1$w'
BASE = '7;19;1;@;@;@;0;2;@;BBBB'
CASES = []
for bank, prefix in enumerate(('(', ')', '*', '+')):
    designators = ['B']*4
    designators[bank] = 'U'
    CASES.append((f'sco-bank-{bank}', RESET+'\x1b'+prefix+'U'+QUERY,
                  DCS+'1$u1;1;1;@;@;@;0;2;@;'+''.join(designators)+ST))
CASES += [
    ('retained-modern-order', RESET+CSI+'2;3;8;9;21;31;44m'+DCS+'1$t'+BASE+ST+QUERY+DCS+'$qm'+ST,
     DCS+'1$u'+BASE+ST+DCS+'1$r0;2;3;8;9;21;31;44m'+ST),
    ('sub-cancels-without-glyph', RESET+DCS+'1$t'+BASE+'\x1a'+QUERY,
     DCS+'1$u1;1;1;@;@;@;0;2;@;BBBB'+ST),
    ('report-modern-underline-as-underlined', RESET+CSI+'4:3;21;58:2::1:2:3m'+QUERY,
     DCS+'1$u1;1;1;B;@;@;0;2;@;BBBB'+ST),
    ('restore-single-keeps-legacy-double-color', RESET+CSI+'4:3;21;58:2::1:2:3m'+
     DCS+'1$t'+BASE.replace(';@;@;@;', ';B;@;@;')+ST+DCS+'$qm'+ST,
     DCS+'1$r0;4;21;58:2::1:2:3m'+ST),
    ('tab-stream-over-query-buffer', RESET+DCS+'2$t'+('2/'*2000)+'79'+ST+CSI+'2$w',
     DCS+'2$u2/79'+ST),
    ('all-visible-tabs', RESET+DCS+'2$t'+'/'.join(map(str,range(2,81)))+ST+CSI+'2$w',
     DCS+'2$u'+'/'.join(map(str,range(2,81)))+ST),
]
