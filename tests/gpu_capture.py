"""Retained GPU frame capture for a fixture-owned process, with local GDI handles.

External PrintWindow can return white for a valid GL frame on Windows. Frida is
test-only; samples taken after attaching include its memory and must be labelled.
This validates the retained framebuffer, not the physical display/compositor.
"""
from native_test_utils import root, c, w, u, struct, capture_result
from frida_test_utils import call_frida, detach_session


class OwnedGPUCapture:
    def __init__(self, pid, hwnd):
        owner = w.DWORD()
        u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        if owner.value != pid:
            raise ValueError('Capture HWND does not belong to the fixture PID')
        import frida
        self.session = call_frida('capture-attach', frida.attach, pid)
        try:
            source = 'const ownedWindow=ptr("'+hex(hwnd)+'");\n'
            self.script = call_frida('capture-create-script', self.session.create_script,
                source+(root/'tests/gpu_capture.js').read_text(encoding='utf-8'))
            call_frida('capture-load-script', self.script.load)
        except BaseException:
            self.close()
            raise

    def capture(self, name=None, return_pixels=False):
        raw = self.script.exports_sync.capture()
        width, height = struct.unpack('<II', raw[:8])
        return capture_result(width, height, raw[8:], name, return_pixels)

    def close(self):
        if self.session is not None:
            detach_session(self.session)
            self.session = None
