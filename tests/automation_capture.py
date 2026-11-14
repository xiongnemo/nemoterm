"""Active-renderer pixels from an explicitly opted-in fixture-owned terminal.

No target injection, window activation or clipboard access. This observes the
terminal's retained renderer surface, not the physical desktop compositor.
"""
from native_test_utils import root, c, w, u, struct, capture_result, wait_for, sys

sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


class OwnedAutomationCapture:
    def __init__(self,pid,hwnd):
        owner=w.DWORD()
        u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        assert u.GetWindowThreadProcessId(hwnd,c.byref(owner)) and owner.value==pid
        instance=wait_for(lambda:next(iter(api.discover(pid)),None))
        assert instance['pid']==pid
        target=next((s for s in instance['sessions'] if s['hwnd']==hwnd),None)
        if not target:raise ValueError('Owned HWND has no automation session')
        self.endpoint=instance['endpoint'];self.session=target['id']

    def capture(self,name=None,return_pixels=False):
        if self.endpoint is None:raise RuntimeError('Capture is closed')
        raw=api.request(self.endpoint,'image',self.session)
        if not isinstance(raw,bytes) or len(raw)<54 or raw[:2]!=b'BM':
            raise ValueError('Expected a renderer BMP')
        size,offset=struct.unpack_from('<I',raw,2)[0],struct.unpack_from('<I',raw,10)[0]
        header,width,height,planes,depth,compression=struct.unpack_from('<IiiHHI',raw,14)
        if (header,offset,planes,depth,compression)!=(40,54,1,32,0) or height>=0 or width<=0:
            raise ValueError('Unsupported renderer BMP layout')
        if size!=len(raw) or len(raw)!=54+width*(-height)*4:
            raise ValueError('Renderer BMP length mismatch')
        return capture_result(width,-height,raw[54:],name,return_pixels)

    def close(self):
        # Each API request closes its pipe before returning; no target-side
        # instrumentation or capture resources are retained between calls.
        self.endpoint=None
