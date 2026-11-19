"""Follow the same printed glyphs across a main-screen soft wrap on a hosted desktop."""
from collections import Counter
from native_test_utils import u, wait_for, time
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, capture, resize, aim, barrier, desk, evidence):
    cw,ch=evidence['cell_pixels'];ack=b'\x1b[0n';cases=evidence['reflow_selection']=[]
    for name, held, block, left in [('stream',False,False,72), ('reverse-press',True,False,72),
                                    ('rectangle',False,True,74), ('split-rectangle',False,True,72)]:
        survives=name!='split-rectangle';tag='reflow-'+name
        row={'case':name,'frames':[]};cases.append(row)
        scene='\x1b[?1049l\x1bc\x1b[3J\x1b[?25l\x1b[3;1H|ABCDEFGH|\x1b[7;70H|ABCDEFGH|\x1b[1;1H\x1b[?1002;1006h'
        begin(tag,scene+'\x1b[?47$p\x1b[?1002$p\x1b[?1006$p',preserve_mouse=True)
        def colours(p, stride, x, y):
            data=b''.join(p[((1+y*ch+i)*stride+1+x*cw)*3:((1+y*ch+i)*stride+1+(x+1)*cw)*3] for i in range(ch))
            return Counter(zip(data[::3],data[1::3],data[2::3]))
        def frame(label,cols,selected):
            stride=2+cw*cols
            def see(p):
                if len(p) != stride*(2+24*ch)*3: return None
                marks=[]
                for i in range(10):
                    ref=colours(p,stride,i,2);x=(69+i)%cols;y=6+(69+i)//cols;actual=colours(p,stride,x,y)
                    if len(ref)<2 or len(actual)<2: return None
                    if ref.most_common(1)[0][0]!=actual.most_common(1)[0][0]: marks.append(i)
                return marks
            until=time.monotonic()+1.5
            while see(capture(return_pixels=True))!=selected and time.monotonic()<until: time.sleep(.04)
            observed=see(capture(tag+'-'+label+'.png',return_pixels=True));row['frames'].append(dict(stage=label,cols=cols,highlight=observed,expected=selected));return observed
        def copy_at(stage):
            begin(tag+'-copy-'+stage,'',preserve_mouse=True)
            seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'))
            return dict(wire=barrier(None),text=clipboard_text(hwnd) if seq!=u.GetClipboardSequenceNumber() else None)
        try:
            assert frame('initial',80,[])==[]
            aim(76 if held else left,6);desk.event(0x10,True)
            if block:desk.event(0x11,True)
            desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            chosen=list(range(left-69,8))
            if not held:
                aim(76,6);desk.event(None,False)
                if block:desk.event(0x11,False)
                desk.event(0x10,False);wait_for(lambda:desk.state().capture!=hwnd)
                assert frame('selected',80,chosen)==chosen
            resize(-6,0)
            if held:
                desk.event(0x10,False);aim(left,6);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
            expected=chosen if survives else [];frame('narrow',74,expected)
            row['gesture_wire']=barrier(None)
            if survives:row['narrow_copy']=copy_at('narrow')
            resize(0,0);frame('wide',80,expected)
            if survives:
                wide=copy_at('wide');row['copy_wire']=wide['wire'];row['copied']=wide['text']
            begin(tag+'-right','',preserve_mouse=True);aim(76,6);seq=u.GetClipboardSequenceNumber();desk.event('right',True)
            try:wait_for(lambda:desk.state().capture==hwnd or seq!=u.GetClipboardSequenceNumber())
            finally:desk.event('right',False)
            wait_for(lambda:desk.state().capture!=hwnd);row['right_wire']=barrier(None);row['right_copy']=clipboard_text(hwnd) if seq!=u.GetClipboardSequenceNumber() else None
            text='|ABCDEFGH|'[left-69:8] if survives else None
            mode=b'\x1b[?47;2$y\x1b[?1002;1$y\x1b[?1006;1$y';wire=b'' if survives else b'\x1b[<2;77;7M\x1b[<2;77;7m'
            row['passed']=(all(f['expected']==f['highlight'] for f in row['frames']) and row['gesture_wire']==(mode+ack*2).hex() and
                           row.get('copied')==text==row['right_copy'] and (not survives or (row['copy_wire']==(ack*2).hex() and row['narrow_copy']==dict(text=text,wire=(ack*2).hex()))) and row['right_wire']==(ack+wire+ack).hex())
        finally:
            for key in reversed(desk.held[:]):desk.event(key,False)
            resize(0,0)
    return all(r['passed'] for r in cases)
