"""Bounded diagnostic observer for a PID just spawned by an owned protocol job.

The JSONL is flushed incrementally, so an assertion or controller timeout keeps
earlier evidence. The observer changes timing and is never memory acceptance.
"""
import hashlib
import json
import threading
import time
from pathlib import Path
import frida
from frida_test_utils import call_frida, detach_session


class ProtocolWireTrace:
    def __init__(self, process, executable, output):
        if process.poll() is not None:
            raise RuntimeError('The owned frontend exited before trace attachment')
        self.output = Path(output)
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.session = None
        self.closed = False
        self.records = 0
        self.io_counts = dict(ReadFile=0, WriteFile=0)
        self.errors = []
        self.truncated = False
        self.file = self.output.open('x', encoding='utf-8', newline='\n')
        self.record(dict(kind='identity', pid=process.pid,
            executable=str(executable), executable_sha256=hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
            frida_version=frida.__version__, diagnostic_only=True, instrumented=True))
        try:
            self.session = call_frida('protocol-wire-attach', frida.attach, process.pid)
            source = Path(__file__).with_suffix('.js').read_text(encoding='utf-8')
            self.script = call_frida('protocol-wire-create', self.session.create_script, source)
            self.script.on('message', self.message)
            call_frida('protocol-wire-load', self.script.load)
            if not self.ready.wait(5):
                raise RuntimeError(('Protocol wire hooks did not report ready', self.errors))
        except BaseException:
            self.close()
            raise

    def record(self, value):
        with self.lock:
            if self.closed:
                return
            value['controller_time_ns'] = time.time_ns()
            self.file.write(json.dumps(value, ensure_ascii=True)+'\n')
            self.file.flush()
            self.records += 1

    def message(self, message, data):
        value = dict(message.get('payload', message))
        if data is not None:
            value['hex'] = data.hex()
        if message['type'] == 'error' or value.get('capture_error'):
            self.errors.append(value)
        if value.get('kind') == 'truncated':
            self.truncated = True
        if value.get('kind') == 'io':
            self.io_counts[value['api']] += 1
        self.record(value)
        if value.get('kind') == 'ready':
            self.ready.set()

    def phase(self, name, sequence, expected):
        self.record(dict(kind='phase', name=name, sequence_hex=sequence.encode().hex(),
                         expected_hex=expected.encode().hex() if expected is not None else None))

    def close(self):
        if not self.closed:
            try:
                if self.session is not None:
                    detach_session(self.session)
                    self.session = None
                self.record(dict(kind='closed', truncated=self.truncated, errors=self.errors,
                                 io_counts=self.io_counts))
            finally:
                with self.lock:
                    self.closed = True
                    self.file.close()
        return dict(path=str(self.output), records=self.records,
                    sha256=hashlib.sha256(self.output.read_bytes()).hexdigest(),
                    truncated=self.truncated, errors=self.errors, io_counts=self.io_counts,
                    diagnostic_only=True)
