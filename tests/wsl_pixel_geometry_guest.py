"""Guest-side observer for the hosted native WSL window. All I/O stays on its own PTY."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import sys
import termios
import time
import tty

folder = Path(sys.argv[1])
query = b'\x1b[16t\x1b[18t\x1b[5n'
reply = re.compile(rb'\x1b\[6;(\d+);(\d+)t\x1b\[8;(\d+);(\d+)t\x1b\[0n')


def size(fd):
    return struct.unpack('=HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, bytes(8)))


def publish(name, state):
    tmp = folder / (name + '.tmp')
    tmp.write_text(json.dumps(state), encoding='utf8')
    tmp.replace(folder / (name + '.json'))


def exercise():
    # Independent of the Windows terminal: ask a separate PTY in this very
    # kernel to retain both pixel fields with the same rows and columns.
    ctl = []
    master, slave = pty.openpty()
    try:
        for dims in [(24, 80, 640, 480), (24, 80, 720, 504), (31, 87, 696, 620)]:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('=HHHH', *dims))
            ctl.append(dict(sent=dims, slave=size(slave)))
    finally:
        os.close(master); os.close(slave)
    # Check both PTY ends independently: a stale master/slave observation
    # doesn't show whether an ioctl on the other end would reach this guest.
    endpoints = {}
    for setter in ('slave','master'):
        master, slave = pty.openpty()
        try:
            samples = endpoints[setter] = []
            for dims in [(24,80,640,480),(24,80,720,504)]:
                fcntl.ioctl(slave if setter=='slave' else master,termios.TIOCSWINSZ,struct.pack('=HHHH',*dims))
                samples.append(dict(sent=dims,master=size(master),slave=size(slave)))
        except OSError as error:
            samples.append(dict(error=str(error),errno=error.errno))
        finally:
            os.close(master); os.close(slave)
    parent = Path('/proc') / str(os.getppid()) / 'exe'
    publish('startup', dict(tty=os.ttyname(0), parent=os.readlink(parent),
        relay_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(), winsize=size(0), kernel_control=ctl, endpoint_control=endpoints))
    for stage in sys.argv[2:]:
        deadline = time.monotonic()+30
        while not (folder / ('request-'+stage)).is_file():
            if (folder/'stop').exists(): return
            if time.monotonic() >= deadline: raise TimeoutError(stage)
            time.sleep(.025)
        first = size(0); os.write(1, query); wire = b''; deadline = time.monotonic()+4
        while not wire.endswith(b'\x1b[0n'):
            if not select.select([0], [], [], max(0, deadline-time.monotonic()))[0]: raise TimeoutError((stage,wire.hex()))
            chunk = os.read(0, 1024)
            if not chunk or len(wire)+len(chunk)>512: raise ValueError((stage,'unexpected input'))
            wire += chunk
        match = reply.fullmatch(wire)
        publish(stage,dict(before=first, after=size(0), reply=wire.hex(),
            cell_grid=list(map(int,match.groups())) if match else None))
    deadline = time.monotonic()+15
    while not (folder/'stop').exists() and time.monotonic()<deadline:time.sleep(.025)


if __name__=='__main__':
    saved = termios.tcgetattr(0)
    try:
        tty.setraw(0); exercise()
    finally: termios.tcsetattr(0, termios.TCSANOW, saved)
