"""Standard-library client for Nemoterm's opt-in local automation pipe."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import zlib

PREFIX = 'Nemoterm.Debug.v1.'
MAX_OUTPUT = 16 * 1024 * 1024
OP = {'list': 1, 'text': 2, 'input': 3, 'paste': 4, 'key': 5, 'image': 6}
k = c.WinDLL('kernel32', use_last_error=True)


class Overlapped(c.Structure):
    _fields_ = [('internal', c.c_size_t), ('high', c.c_size_t),
                ('offset', w.DWORD), ('offset_high', w.DWORD), ('event', w.HANDLE)]


for name, args, result in [
    ('CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
    ('CreateEventW', [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
    ('CloseHandle', [w.HANDLE], w.BOOL),
    ('ReadFile', [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.POINTER(Overlapped)], w.BOOL),
    ('WriteFile', [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.POINTER(Overlapped)], w.BOOL),
    ('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD),
    ('GetOverlappedResult', [w.HANDLE, c.POINTER(Overlapped), c.POINTER(w.DWORD), w.BOOL], w.BOOL),
    ('CancelIoEx', [w.HANDLE, c.POINTER(Overlapped)], w.BOOL),
    ('GetNamedPipeServerProcessId', [w.HANDLE, c.POINTER(w.ULONG)], w.BOOL),
    ('WaitNamedPipeW', [w.LPCWSTR, w.DWORD], w.BOOL),
    ('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
    ('GetProcessTimes', [w.HANDLE]+[c.POINTER(c.c_uint64)]*4, w.BOOL),
]:
    fn = getattr(k, name); fn.argtypes = args; fn.restype = result


class DebugError(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message); self.status = status


def _transfer(handle, value, *, write=False, timeout=6):
    length = len(value) if write else value
    buf = c.create_string_buffer(value, length) if write else c.create_string_buffer(length)
    pos = 0
    deadline = time.monotonic()+timeout
    while pos < length:
        event = k.CreateEventW(None, True, False, None)
        if not event:
            raise c.WinError(c.get_last_error())
        ov = Overlapped(event=event); done = w.DWORD()
        try:
            ok = (k.WriteFile if write else k.ReadFile)(handle, c.byref(buf, pos), length-pos, c.byref(done), c.byref(ov))
            if not ok:
                error = c.get_last_error()
                if error != 997:
                    raise c.WinError(error)
                remaining = max(0, int((deadline-time.monotonic())*1000))
                if k.WaitForSingleObject(event, remaining) != 0:
                    k.CancelIoEx(handle, c.byref(ov))
                    k.GetOverlappedResult(handle, c.byref(ov), c.byref(done), True)
                    raise TimeoutError('Nemoterm pipe operation timed out')
                if not k.GetOverlappedResult(handle, c.byref(ov), c.byref(done), False):
                    raise c.WinError(c.get_last_error())
            if not done.value:
                raise EOFError('Nemoterm closed the connection')
            pos += done.value
        finally:
            k.CloseHandle(event)
    return buf.raw


def connect(endpoint, timeout=6):
    match = re.fullmatch(re.escape(PREFIX)+r'(\d+)\.([0-9a-fA-F]{16})', endpoint)
    if not match:
        raise ValueError('Expected a local Nemoterm.Debug.v1 endpoint name')
    path = '\\\\.\\pipe\\'+endpoint
    deadline = time.monotonic()+timeout
    while True:
        # SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION prevents the server
        # impersonating a more privileged client. All I/O is cancellable.
        handle = k.CreateFileW(path, 0xc0000000, 0, None, 3, 0x40000000|0x100000|0x10000, None)
        if handle != c.c_void_p(-1).value:
            break
        error = c.get_last_error()
        if error != 231 or time.monotonic() >= deadline:
            raise c.WinError(error)
        k.WaitNamedPipeW(path, 100)
    try:
        pid = w.ULONG()
        if not k.GetNamedPipeServerProcessId(handle, c.byref(pid)) or pid.value != int(match[1]):
            raise RuntimeError('Pipe server PID does not match its discovery identity')
        process = k.OpenProcess(0x1000, False, pid.value)
        if not process:
            raise c.WinError(c.get_last_error())
        try:
            times = [c.c_uint64() for _ in range(4)]
            if not k.GetProcessTimes(process, *(c.byref(t) for t in times)) or times[0].value != int(match[2], 16):
                raise RuntimeError('Pipe process creation time does not match its discovery identity')
        finally:
            k.CloseHandle(process)
        return handle
    except BaseException:
        k.CloseHandle(handle)
        raise


def request(endpoint, operation='list', session=0, payload=b''):
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    if len(payload) > 65536:
        raise ValueError('Input exceeds 65536 bytes')
    handle = connect(endpoint)
    try:
        header = struct.pack('<4sHHQII', b'NDBG', 1, OP[operation], session, len(payload), 0)
        _transfer(handle, header+payload, write=True)
        magic, version, status, length, kind = struct.unpack('<4sHHII', _transfer(handle, 16))
        if magic != b'NDBG' or version != 1 or length > MAX_OUTPUT or kind not in (1, 2, 3):
            raise RuntimeError('Invalid automation response')
        response = _transfer(handle, length)
        _transfer(handle, b'\0', write=True)
        value = json.loads(response) if kind == 1 else response.decode('utf-8') if kind == 3 else response
        if status:
            raise DebugError(status, value.get('error', 'Request failed'))
        return value
    finally:
        k.CloseHandle(handle)


def discover(pid=None):
    result = []
    for name in sorted(os.listdir('\\\\.\\pipe\\')):
        if not name.startswith(PREFIX) or (pid is not None and not name.startswith(PREFIX+str(pid)+'.')):
            continue
        try:
            value = request(name)
            value['endpoint'] = name
            result.append(value)
        except (OSError, RuntimeError, TimeoutError, EOFError):
            continue  # An instance can exit between enumeration and connection.
    return result


def png_from_bmp(data):
    """Convert our bounded top-down BGRA BMP to PNG without a codec dependency."""
    if len(data) < 54 or data[:2] != b'BM':
        raise ValueError('Expected a BMP image')
    size, offset = struct.unpack_from('<I4xI', data, 2)
    dib, width, height, planes, bits, compression = struct.unpack_from('<IiiHHI', data, 14)
    if (size != len(data) or offset != 54 or dib != 40 or width <= 0 or height >= 0
            or planes != 1 or bits != 32 or compression != 0 or len(data) != 54+width*(-height)*4):
        raise ValueError('Unexpected BMP layout')
    raw = bytearray()
    for y in range(-height):
        raw.append(0)
        row = data[54+y*width*4:54+(y+1)*width*4]
        for x in range(width):
            raw.extend((row[x*4+2], row[x*4+1], row[x*4]))
    def chunk(name, content):
        return struct.pack('>I', len(content))+name+content+struct.pack('>I', zlib.crc32(name+content))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', width, -height, 8, 2, 0, 0, 0))
            +chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['discover', *OP])
    parser.add_argument('--endpoint')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--session', type=int, default=0)
    parser.add_argument('--text')
    parser.add_argument('--file', type=Path, help='UTF-8 input file')
    parser.add_argument('--vk', type=lambda s: int(s, 0))
    parser.add_argument('--ctrl', action='store_true')
    parser.add_argument('--shift', action='store_true')
    parser.add_argument('--alt', action='store_true')
    parser.add_argument('--output', type=Path, help='Image .png or .bmp destination')
    args = parser.parse_args()
    if args.operation == 'discover':
        print(json.dumps(discover(args.pid), ensure_ascii=False, indent=2));return
    if not args.endpoint:
        parser.error('--endpoint is required; use discover first')
    if args.operation != 'list' and not args.session:
        parser.error('--session is required; use list first')
    payload = b''
    if args.operation in ('input', 'paste'):
        if (args.text is None) == (args.file is None):
            parser.error('provide one of --text or --file')
        payload = args.file.read_bytes() if args.file else args.text
    elif args.operation == 'key':
        if args.vk is None:
            parser.error('--vk is required (Windows virtual key number)')
        payload = struct.pack('<II', args.vk, args.shift | args.ctrl << 1 | args.alt << 2)
    elif args.operation == 'image' and (not args.output or args.output.suffix.lower() not in ('.png', '.bmp')):
        parser.error('image requires --output with .png or .bmp extension')
    value = request(args.endpoint, args.operation, args.session, payload)
    if isinstance(value, bytes):
        args.output.write_bytes(png_from_bmp(value) if args.output.suffix.lower() == '.png' else value)
        print(args.output.resolve())
    elif isinstance(value, str):
        sys.stdout.reconfigure(encoding='utf-8');print(value, end='')
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
