"""Specification/source-derived expectations, NOT captured XTerm evidence.

All cases start with known selection colours, independently of theme defaults.
The separate reference collector must be run before claiming XTerm parity.
"""
CSI = '\x1b['
OSC = '\x1b]'
ST = '\x1b\\'
BEL = '\x07'
QUERY = OSC+'17;?'+ST+OSC+'19;?'+ST
PREFIX = CSI+'?5l'+OSC+'17;#112233'+ST+OSC+'19;#445566'+ST
BG = OSC+'17;rgb:1111/2222/3333'+ST
FG = OSC+'19;rgb:4444/5555/6666'+ST
RED = 'rgb:ffff/0000/0000'
BLUE = 'rgb:0000/0000/ffff'

CASES = [
    ('query-known', QUERY, BG+FG),
    ('query-bel', OSC+'17;?'+BEL+OSC+'19;?'+BEL,
     BG.replace(ST, BEL)+FG.replace(ST, BEL)),
    ('set-background', OSC+'17;red'+ST+QUERY, OSC+'17;'+RED+ST+FG),
    ('set-foreground', OSC+'19;blue'+BEL+QUERY, BG+OSC+'19;'+BLUE+ST),
    ('chain-across-tek-slot', OSC+'17;red;#abcdef;blue'+ST+QUERY,
     OSC+'17;'+RED+ST+OSC+'19;'+BLUE+ST),
    ('chain-empty-tek-slot', OSC+'17;red;;blue'+ST+QUERY,
     OSC+'17;'+RED+ST+OSC+'19;'+BLUE+ST),
    ('chain-empty-background', OSC+'17;;;blue'+ST+QUERY, BG+OSC+'19;'+BLUE+ST),
    ('chain-query-across-gap', OSC+'17;?;;?'+ST, BG+FG),
    ('chain-query-bel-across-gap', OSC+'17;?;;?'+BEL,
     BG.replace(ST, BEL)+FG.replace(ST, BEL)),
    ('chain-from-default-colours', OSC+'10;#ffffff;#000000;red;;;;;red;;blue'+ST+QUERY,
     OSC+'17;'+RED+ST+OSC+'19;'+BLUE+ST),
    ('pointer-and-tek-not-aliases', OSC+'13;red;blue;red;blue'+ST+OSC+'18;red'+ST+QUERY,
     BG+FG),
    ('extra-parameters-ignored', OSC+'19;blue;red;#abcdef'+ST+QUERY,
     BG+OSC+'19;'+BLUE+ST),
    ('empty-values-ignored', OSC+'17;'+ST+OSC+'19;'+ST+QUERY, BG+FG),
    ('invalid-values-ignored', OSC+'17;#xyzxyz'+ST+OSC+'19;rgb:zz/ff/ff'+ST+QUERY, BG+FG),
    ('rgb-short-components', OSC+'17;rgb:1/2/3'+ST+OSC+'19;rgb:4/5/6'+ST+QUERY,
     BG+FG),
    ('cancel-can', OSC+'17;red\x18'+QUERY, BG+FG),
    ('cancel-sub', OSC+'19;blue\x1a'+QUERY, BG+FG),
    ('reverse-queries', CSI+'?5h'+QUERY+CSI+'?5l',
     OSC+'17;rgb:4444/5555/6666'+ST+OSC+'19;rgb:1111/2222/3333'+ST),
    ('reverse-set-background', CSI+'?5h'+OSC+'17;red'+ST+CSI+'?5l'+QUERY,
     BG+OSC+'19;'+RED+ST),
    ('reverse-set-foreground', CSI+'?5h'+OSC+'19;blue'+ST+CSI+'?5l'+QUERY,
     OSC+'17;'+BLUE+ST+FG),
    ('ris-retains', '\x1bc'+QUERY, BG+FG),
    ('decstr-retains', CSI+'!p'+QUERY, BG+FG),
    ('alternate-shared', CSI+'?1049h'+QUERY+CSI+'?1049l'+QUERY, (BG+FG)*2),
    ('sgr-reset-retains', CSI+'0m'+QUERY, BG+FG),
    ('indexed-reset-independent', OSC+'104'+ST+QUERY, BG+FG),
    ('default-reset-independent', OSC+'110'+ST+OSC+'111'+ST+OSC+'112'+ST+QUERY, BG+FG),
    ('other-dynamic-resets-independent', OSC+'113'+ST+OSC+'114'+ST+
     OSC+'115'+ST+OSC+'116'+ST+OSC+'118'+ST+QUERY, BG+FG),
    ('stack-roundtrip', CSI+'1#P'+OSC+'17;red;;blue'+ST+CSI+'1#Q'+QUERY, BG+FG),
    ('indexed-slot-ten', CSI+'10#P'+OSC+'17;red;;blue'+ST+CSI+'10#Q'+QUERY, BG+FG),
    ('stack-repeated-index', CSI+'1#P'+OSC+'17;red;;blue'+ST+CSI+'1#Q'+
     OSC+'17;blue;;red'+ST+CSI+'1#Q'+QUERY, BG+FG),
]
CASES = [(name, PREFIX+sequence, expected) for name, sequence, expected in CASES]
