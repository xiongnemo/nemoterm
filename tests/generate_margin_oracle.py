"""Generate C expectations from an independent XTerm margin capture."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=json.loads((root/'research/margins-xterm.json').read_text(encoding='utf-8'))
flags={1:'ATTR_BOLD',2:'ATTR_DIM',3:'ATTR_ITALIC',4:'ATTR_UNDER',5:'ATTR_BLINK',7:'ATTR_REVERSE',8:'ATTR_CONCEAL',9:'ATTR_STRIKE'}
def literal(s):
    return '"'+''.join('\\%03o'%b if b<32 or b>=127 else '\\'+chr(b) if chr(b) in '\\"' else chr(b) for b in s.encode())+'"'
lines=['/* Generated from '+source['version']+' by tests/generate_margin_oracle.py. */',
       'static const struct { const char *name, *sequence, *reply; unsigned chars[84], attrs[84]; bool check_attrs; } margin_oracle[] = {']
for name,case in source['cases'].items():
    # Resize is exercised through term_size. Saving 69 while off exposes a
    # reference bug (it saves a constant bit); NemoTerm preserves the boolean.
    # scrollInMargins also clears split wide glyphs in row+amount beyond the
    # vertical region. Direct tests require those outside rows to survive.
    if name in ('resize','restore-mode-disabled','wide-left-scroll','wide-right-scroll'):continue
    sequence=case['sequence'].rsplit('\x1b[?6l\x1b[?69l\x1b[31#y',1)[0]
    chars=','.join(str(ord(ch)) for row in case['rows'] for ch in row)
    attrs=','.join('|'.join(flags[n] for n in map(int,s.split(';')) if n in flags) or '0' for s in case.get('attrs',[])) or '0'
    lines.append('  {'+literal(name)+','+literal(sequence)+','+literal(case['state_reply'])+',{'+chars+'},{'+attrs+'},'+('true' if 'attrs' in case else 'false')+'},')
lines.append('};')
(root/'tests/margin_oracle_cases.h').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
