"""Double-size row output through the actual single-image ConPTY path."""
from protocol_oracle_window import run
from double_size_oracle_cases import CASES

scene = ('\x1bc\x1b[?25l\x1b[1;1HDOUBLE-SIZE ROWS / CJK / COMBINING\r\n'
    '\x1b[3;1H\x1b#6\x1b[36m' + 'A'*39 + '中' + '\x1b[0m normal row after wrap'
    '\x1b[6;1H\x1b#3\x1b[33mDouble height: 中文 e\u0301 0123456789'
    '\x1b[7;1H\x1b#4Double height: 中文 e\u0301 0123456789\x1b[0m'
    '\x1b[10;1H\x1b#6\x1b[32m' + 'B'*39 + 'e\u0301Z' + '\x1b[0m normal row after accent'
    '\x1b[14;1H108 tabulation + 45 double-size reference cases')
direct = [('destination-row-width', '\x1bc\x1b#6'+'A'*40+'B'*80+'\x1b[6nC\x1b[6n',
           '\x1b[2;80R\x1b[3;2R')]
run('double-size', CASES, scene, direct)
