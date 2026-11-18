"""Read the two Sixel swatches from the running settings fixture's own renderer."""
import argparse, json
from automation_capture import OwnedAutomationCapture
from native_test_utils import c, w, u, wait_for

parser=argparse.ArgumentParser()
parser.add_argument('pid', type=int); parser.add_argument('hwnd', type=int)
parser.add_argument('cell_height', type=int); parser.add_argument('colour', choices=('green','blue'))
parser.add_argument('phase', choices=('sixel-settings-startup','sixel-settings-disabled','sixel-settings-reloaded-dx'))
a=parser.parse_args(); surface=OwnedAutomationCapture(a.pid,a.hwnd)
red=bytes((255,0,0)); expected={'green':bytes((51,204,51)),'blue':bytes((0,0,255))}[a.colour]
assert a.cell_height>0
last={}
def observe(name=None):
    rect=w.RECT(); assert u.GetClientRect(a.hwnd,c.byref(rect))
    rgb=surface.capture(name,return_pixels=True); width=rect.right
    if len(rgb)!=width*rect.bottom*3: return None
    # Row 2 is always red. Locate it in the actual frame (independent of
    # borders and tab placement); row 6 must share the same left edge.
    match=rgb.find(red*8)
    while match>=0 and match%3: match=rgb.find(red*8,match+1)
    if match<0: return None
    y,x=divmod(match//3,width); second=y+4*a.cell_height
    if x+8>width or second+6>rect.bottom: return None
    def swatch(top): return b''.join(rgb[(row*width+x)*3:(row*width+x+8)*3] for row in range(top,top+6))
    first=swatch(y); following=swatch(second)
    last.update(reference_origin=[x,y],next_origin=[x,second],reference_red_pixels=sum(first[i:i+3]==red for i in range(0,len(first),3)),next_expected_pixels=sum(following[i:i+3]==expected for i in range(0,len(following),3)),next_first_rgb=following[:3].hex())
    return last.copy() if first==red*48 and following==expected*48 else None
try:
    try:
        wait_for(observe)
    except AssertionError as error:
        observe(a.phase+'.png')
        raise AssertionError((a.phase, a.colour, last)) from error
    result=observe(a.phase+'.png')
    assert result, (a.phase,last)
    print(json.dumps(dict(phase=a.phase,colour=a.colour,**result)))
finally:surface.close()
