"""DEC reports through the actual console host, including live resized grids."""
from dec_status_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, terminal_host, time, u, wait_for

direct = [
    ('udk-unavailable', '\x1b[65;1"p\x1b[?25n', '\x1b[?23n'),
    ('empty-checksum-id', '\x1b[?63;;9n', '\x1bP0!~0000\x1b\\'),
    ('stale-internal-reply-is-consumed', '\x1b[?9001;65535n', ''),
]


def exercise(hwnd, phase, current):
    evidence = {}
    report='\x1b[6n\x1b[?6n'

    def corner(name):
        cols,rows=current()['columns'],current()['rows']
        reply=f'\x1b[{rows};{cols}R\x1b[?{rows};{cols};1R'
        phase(name,'\x1b[999;999H'+report,reply)
        evidence[name]=dict(grid=[cols,rows],reply=reply)
        return cols,rows

    phase('geometry-reset','\x1bc','')
    before=corner('initial-corner')
    assert u.MoveWindow(terminal_host(hwnd),40,40,700,500,True)
    wait_for(lambda:(current()['columns'],current()['rows'])!=before)
    cols,rows=corner('resized-corner')
    # Margins are 1-based: top=3/bottom=rows-2, left=5/right=cols-3.
    reply=f'\x1b[{rows-4};{cols-7}R\x1b[?{rows-4};{cols-7};1R'
    phase('resized-origin',f'\x1b[3;{rows-2}r\x1b[?69h\x1b[5;{cols-3}s'
          '\x1b[?6h\x1b[999;999H'+report,reply)
    evidence['resized-origin']=dict(grid=[cols,rows],reply=reply)

    # Force unknown-sequence synchronization while application CPRs are also
    # pending. Host GetConsoleScreenBufferInfo must see absolute coordinates;
    # the application must receive exactly its own reports, in wire order.
    stress=[]
    for index in range(80):
        row,col=1+index%(rows-4),1+index%(cols-7)
        reply=f'\x1b[{row};{col}R\x1b[?{row};{col};1R'
        phase(f'cursor-sync-{index}', f'\x1b[{row};{col}H\x1b[99999z'+report, reply)
        wanted=[col+3,row+1]
        wait_for(lambda:current().get('screen_cursor')==wanted)
        stress.append(dict(origin_cursor=[col,row],host_cursor=wanted))
    evidence['cursor_sync']=stress

    phase('visible-content','\x1bc\x1b[?25l\x1b[2;3H\x1b[36m'
          'DEC STATUS / content preserved / 0123456789\x1b[0m','')
    time.sleep(.2)
    pixels_before=capture(hwnd,return_pixels=True)
    phase('queries-preserve-content', ''.join(f'\x1b[?{n}n' for n in
          (5,15,25,26,55,56,62,63,75,85)),
          '\x1b[?0n\x1b[?13n\x1b[?23n\x1b[?27;1;0;0n\x1b[?53n'
          '\x1b[?57;0n\x1b[0000*{\x1bP0!~0000\x1b\\\x1b[?70n\x1b[?83n')
    pixels_after=capture(hwnd,'dec-status-window.png',return_pixels=True)
    assert pixels_before==pixels_after
    evidence['content_rgb_sha256']=hashlib.sha256(pixels_after).hexdigest()
    return evidence


run('dec-status',CASES,extra_cases=direct,exercise=exercise,
    barrier=('\x1b[>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'), report_cursor=True)
