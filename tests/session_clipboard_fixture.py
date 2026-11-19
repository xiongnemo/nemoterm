"""Exercise asynchronous paste via the real clipboard and the public Paste menu."""
from contextlib import contextmanager
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from clipboard_test_utils import SavedClipboard, set_clipboard
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import root, u, wait_for


def request_paste(hwnd):
    u.SendMessageW(hwnd, 0x111, 0x01A0, 0)  # WM_COMMAND / IDM_PASTE


@contextmanager
def pending_paste(hwnd, keeper, text, record):
    """Wait for GetClipboardData before yielding. keeper stays open throughout."""
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    saved = SavedClipboard(keeper)
    with tempfile.TemporaryDirectory() as work:
        state, control = (Path(work) / f'{n}.json' for n in ('state', 'control'))
        helper = subprocess.Popen([sys.executable, str(root/'tests/osc52_delayed_fixture.py'),
            str(state), str(control), '--long-hold', '--text', text],
            creationflags=subprocess.CREATE_NO_WINDOW)
        owner = None
        def release():
            assert read_snapshot(state).get('state') == 'rendering', 'clipboard owner released before session transition'
            write_snapshot(control, {'release': True})
            wait_for(lambda: read_snapshot(state).get('state') == 'rendered')
            # The text worker sends its reply synchronously before closing the clipboard.
            wait_for(lambda: u.OpenClipboard(keeper))
            try:
                assert u.GetClipboardOwner() == owner
                record['released_after_transition'] = True
            finally: u.CloseClipboard()
        try:
            wait_for(lambda: read_snapshot(state).get('state') == 'ready')
            owner = read_snapshot(state)['hwnd']
            assert u.GetClipboardOwner() == owner
            request_paste(hwnd)
            wait_for(lambda: read_snapshot(state).get('state') == 'rendering')
            record.update(request_hwnd=hwnd, owner_pid=helper.pid, read_started=True, stale_text=text)
            yield release
        finally:
            try:
                write_snapshot(control, {'release': True})
                wait_for(lambda: u.OpenClipboard(keeper))
                try:
                    if owner and u.GetClipboardOwner() == owner:
                        assert u.EmptyClipboard()  # transfer the fixture's clipboard back to keeper
                finally: u.CloseClipboard()
                saved.restore()
            finally:
                write_snapshot(control, {'release': True, 'stop': True})
                try: helper.wait(timeout=6)
                except subprocess.TimeoutExpired: helper.kill(); helper.wait(); raise
                assert helper.returncode == 0


def check_receivers(target, peer, keeper, stale, fresh, barrier, record):
    for seat in (target, peer):
        received = bytes.fromhex(barrier(seat)['hex'])
        assert stale.encode() not in received, (stale, received)
    set_clipboard(keeper, fresh)
    request_paste(target['hwnd'])
    wait_for(lambda: fresh.encode() in bytes.fromhex(read_snapshot(target['report']).get('hex', '')))
    for label, seat, count in (('target',target,1), ('peer',peer,0)):
        received = bytes.fromhex(barrier(seat)['hex'])
        record[label+'_hex'] = received.hex()
        assert received.count(fresh.encode()) == count and stale.encode() not in received, (label, received)
