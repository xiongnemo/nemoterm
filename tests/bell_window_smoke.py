"""Observe real bell API calls in owned CI terminals, without replacing them."""
import frida
from protocol_oracle_window import run
from native_test_utils import c, w, u

u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]

def exercise_for(mode):
    def exercise(hwnd, phase, current):
        pid = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        session = frida.attach(pid.value)
        try:
            script = session.create_script('''
                const events = [];
                const address = Process.getModuleByName('user32.dll').getExportByName('MessageBeep');
                Interceptor.attach(address, {onEnter(args) {this.kind=args[0].toUInt32();},
                    onLeave(result) {events.push({api:'MessageBeep',kind:this.kind,result:result.toInt32()});}});
                rpc.exports = {events() {return events;}};
            ''')
            script.load()
            phase('osc-terminator', '\x1b]2;bell-test\x07', '')
            assert script.exports_sync.events() == []
            phase('ordinary-bel', '\x07', '')
            events = script.exports_sync.events()
            if mode == 1:
                assert len(events) == 1 and events[0]['kind'] == 0, events
            else:
                assert events == [], events
            return dict(bell_mode=mode, api_events=events,
                        observation='actual API invocation; no API return replacement; audible speaker output unverified')
        finally:
            session.detach()
    return exercise

for mode in (0,1,2):
    run('bell-mode-'+str(mode), (), exercise=exercise_for(mode),
        profile=dict(Beep=mode, BellOverload=0, WarnOnClose=0),
        source_reference='PuTTY BEL policy and real Windows MessageBeep observation')
