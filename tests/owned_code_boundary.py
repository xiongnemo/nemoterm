"""Read-only PE executable-section comparison in a retained fixture-owned process.

The controller retains baseline code privately. Evidence contains hashes and at
most 64 changed 32-byte blocks per snapshot, never terminal data or heap pages.
No injection, suspension, target calls or writes are performed by this observer.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import struct
import time
from thread_snapshot import OwnedThreadSnapshot, modules


class OwnedCodeBoundary:
    def __init__(self, process, job):
        self.owner = OwnedThreadSnapshot(process, job).owner
        self.process = process
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p,
            c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
        self.sections = []
        self.started = time.monotonic()
        catalogue = modules(self.owner.handle)
        selected = [m for m in catalogue if m['base'] == catalogue[0]['base'] or
                    m['name'].lower() in ('ntdll.dll', 'user32.dll', 'kernelbase.dll')]
        if not any(m['name'].lower() == 'ntdll.dll' for m in selected):
            raise RuntimeError('Owned process has no ntdll baseline')
        total = 0
        for module in selected:
            base, size = module['base'], module['size']
            dos = self.read(base, 64)
            if dos[:2] != b'MZ': raise ValueError('Invalid mapped DOS header')
            offset, = struct.unpack_from('<I', dos, 60)
            if not 64 <= offset <= min(size-24, 1048576):
                raise ValueError('Invalid mapped PE offset')
            header = self.read(base+offset, 24)
            if header[:4] != b'PE\0\0': raise ValueError('Invalid mapped PE signature')
            machine, count = struct.unpack_from('<HH', header, 4)
            optional, = struct.unpack_from('<H', header, 20)
            if machine != 0x8664 or not 1 <= count <= 96 or not 112 <= optional <= 4096:
                raise ValueError('Unexpected mapped PE shape')
            table = offset+24+optional
            if table+40*count > size: raise ValueError('Invalid section table range')
            entries = self.read(base+table, 40*count)
            for index in range(count):
                name, length, rva = struct.unpack_from('<8sII', entries, index*40)
                flags, = struct.unpack_from('<I', entries, index*40+36)
                if not flags & 0x20000000 or not length: continue
                if rva+length > size or length > 16*1024*1024:
                    raise ValueError('Executable section outside bounded image')
                total += length
                if total > 32*1024*1024: raise ValueError('Code baseline exceeds 32 MiB')
                data = self.read(base+rva, length)
                self.sections.append(dict(module=module['name'], base=base,
                    section=name.rstrip(b'\0').decode('ascii'), rva=rva, bytes=length,
                    baseline_sha256=hashlib.sha256(data).hexdigest(), data=data))
        self.identity = dict(modules=selected, bytes=total,
            sections=[{k:v for k,v in s.items() if k != 'data'} for s in self.sections],
            controller_only=True, baseline_seconds=time.monotonic()-self.started)

    def read(self, address, length):
        self.owner._validate_owner()
        data, read = c.create_string_buffer(length), c.c_size_t()
        if not self.kernel.ReadProcessMemory(self.owner.handle, address, data,
                                            length, c.byref(read)):
            raise c.WinError(c.get_last_error())
        if read.value != length: raise RuntimeError('Partial owned code read')
        return data.raw

    def snapshot(self, label):
        started = time.monotonic()
        result = dict(label=label, pid=self.process.pid, sections=[], changes=[],
                      changed_blocks=0, exit_code=self.process.poll())
        if result['exit_code'] is not None: return result
        try:
            for section in self.sections:
                address = section['base']+section['rva']
                current = self.read(address, section['bytes'])
                baseline = section['data']
                result['sections'].append(dict(module=section['module'],
                    section=section['section'], sha256=hashlib.sha256(current).hexdigest(),
                    matches_baseline=current == baseline))
                if current == baseline: continue
                for page in range(0, len(current), 4096):
                    if current[page:page+4096] == baseline[page:page+4096]: continue
                    for offset in range(page, min(page+4096, len(current)), 32):
                        before, after = baseline[offset:offset+32], current[offset:offset+32]
                        if before == after: continue
                        result['changed_blocks'] += 1
                        if len(result['changes']) < 64:
                            result['changes'].append(dict(module=section['module'],
                                section=section['section'], rva=section['rva']+offset,
                                address=address+offset, before=before.hex(), after=after.hex()))
            result['omitted_blocks'] = result['changed_blocks']-len(result['changes'])
        except Exception as error:
            result['observation_error'] = repr(error)
        result.update(seconds=time.monotonic()-started,
                      exit_code_after_observation=self.process.poll())
        return result
