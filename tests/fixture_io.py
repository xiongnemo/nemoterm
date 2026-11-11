"""Small JSON mailbox for Windows fixture processes.

Windows may deny replacement while another process briefly reads the file.
Keep atomic snapshots, retry that sharing violation, and bound every wait.
"""
import json
import os
import time


def write_snapshot(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    deadline = time.monotonic() + 2
    while True:
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def read_snapshot(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}
