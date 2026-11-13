"""Bounded test-only Frida handle lifetime trace for a retained owned process."""
import hashlib
import json
from pathlib import Path
from handle_snapshot import OwnedHandleSnapshot
from frida_test_utils import call_frida, detach_session


class OwnedHandleTrace:
    def __init__(self, process, job, output):
        self.owner = OwnedHandleSnapshot(process, job)
        self.output = Path(output)
        self.session = None
        self.script = None
        self.result = dict(pid=process.pid, injected=True, memory_acceptance=False,
                           messages=[], dropped_messages=0, completed=False, detached=False)
        source = Path(__file__).with_suffix('.js').read_bytes()
        self.result['script_sha256'] = hashlib.sha256(source).hexdigest()
        import frida
        self.result['frida_python'] = frida.__version__
        try:
            self.session = call_frida('handle-attach', frida.attach, process.pid)
            self.script = call_frida('handle-create-script', self.session.create_script, source.decode('utf-8'))
            def message(message, data):
                if len(self.result['messages']) < 32:
                    self.result['messages'].append(message)
                else:
                    self.result['dropped_messages'] += 1
            self.script.on('message', message)
            call_frida('handle-load-script', self.script.load)
        except BaseException:
            if self.session:
                detach_session(self.session)
            raise

    def mark(self, label):
        self.owner._validate_owner()
        # RPC has the enclosing owned-fixture deadline; Frida's Cancellable
        # cannot bound exports_sync. See frida_test_utils.py.
        return self.script.exports_sync.mark(label)

    def close(self):
        if self.session is None:
            return self.result
        try:
            self.result['trace'] = self.script.exports_sync.stop()
            self.result['completed'] = (not self.result['messages'] and
                not self.result['trace']['overflow'] and self.result['trace']['stopReason'] == 'caller')
        finally:
            try:
                detach_session(self.session)
                self.result['detached'] = self.session.is_detached
            finally:
                self.session = None
                self.output.parent.mkdir(parents=True, exist_ok=True)
                self.output.write_text(json.dumps(self.result, indent=2)+'\n', encoding='utf-8')
        return self.result
