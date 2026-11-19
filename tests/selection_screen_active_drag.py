"""Actual Windows drag is still in progress when the console child writes a screen request."""
from native_test_utils import u, wait_for
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, received, point, capture, tile, barrier, desktop, evidence):
    cases=evidence['screen_active_drag']=[]
    ack=b'\x1b[0n'
    pattern='\x1b[7;1H|ABCDE|\x1b[9;1H|ABCDE|'
    def motion(x):
        p=point(x,6); desktop.point(p & 0xffff,p >> 16)
    def changes(p):return [x for x in range(7) if tile(p,x,6)!=tile(p,x,8)]
    for name, alt, command, survives, target in (
        ('main-repeat',False,'?47l',True,False),('enter',False,'?47h',False,True),
        ('alternate-repeat',True,'?1047h',True,True),('alternate-clear',True,'?1049h',False,True),
    ):
        tag='screen-drag-'+name; row=dict(case=name,command=command);cases.append(row)
        begin(tag+'-start', '\x1b[?1049l\x1bc\x1b[?25l'+pattern+'\x1b[?47h'+pattern+
              ('' if alt else '\x1b[?47l')+'\x1b[?1002;1006h')
        def drawn():
            p=capture(return_pixels=True)
            return not changes(p) and all(len(set(tile(p,x,8)))>1 for x in range(1,6))
        wait_for(drawn);motion(2);desktop.event(0x10,True);desktop.event(None,True)
        try:
            wait_for(lambda: desktop.state().capture==hwnd);motion(3)
            wait_for(lambda: changes(capture(return_pixels=True))==[2,3]);row['before']=changes(capture(tag+'-before.png',return_pixels=True))
            # Child publishes this phase only AFTER printing/flushing its VT.
            # Do not require a DSR response before releasing the left button:
            # a frontend may hold terminal output while the user is selecting.
            action='\x1b['+command+(pattern if name=='alternate-clear' else '')
            mode=tag+'-request';sent=begin(mode,action+'\x1b[?47$p',preserve_mouse=True,wait_reply=False)
            row['wire_while_down']=sent['hex'];row['captured_while_written']=desktop.state().capture==hwnd
            desktop.event(0x10,False);motion(4);desktop.event(None,False)
            wait_for(lambda: desktop.state().capture!=hwnd);received(mode)
            row['application_wire']=barrier(None)
            expected=[2,3,4] if survives else []
            # Wait for the GUI separately from the ordered response channel.
            from time import monotonic,sleep
            until=monotonic()+1.5
            while changes(capture(return_pixels=True))!=expected and monotonic()<until:sleep(.03)
            row['after']=changes(capture(tag+'-after.png',return_pixels=True))
            if survives:
                begin(tag+'-copy','',preserve_mouse=True);seq=u.GetClipboardSequenceNumber()
                desktop.chord(0x11,0x10,ord('C'));row['copy_wire']=barrier(None)
                row['copied']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seq else None
            begin(tag+'-right','',preserve_mouse=True);seq=u.GetClipboardSequenceNumber();desktop.event('right',True)
            try:wait_for(lambda: desktop.state().capture==hwnd or u.GetClipboardSequenceNumber()!=seq)
            finally:desktop.event('right',False)
            wait_for(lambda: desktop.state().capture!=hwnd);row['right_wire']=barrier(None)
            row['right_copy']=clipboard_text(hwnd) if seq!=u.GetClipboardSequenceNumber() else None
            mode_reply=b'\x1b[?47;'+(b'1' if target else b'2')+b'$y'
            right=b'' if survives else b'\x1b[<2;5;7M\x1b[<2;5;7m'
            row['passed']=(row['before']==[2,3] and row['captured_while_written'] and row['after']==expected and
                           row['application_wire']==(mode_reply+ack*2).hex() and
                           (not survives or row.get('copy_wire')==(ack*2).hex()) and
                           row.get('copied')==row['right_copy']==('BCD' if survives else None) and
                           row['right_wire']==(ack+right+ack).hex())
        finally:
            for key in reversed(desktop.held[:]):desktop.event(key,False)
    return all(r['passed'] for r in cases)
