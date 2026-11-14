"""Capture compression behavior from pinned, compiled upstream kitty via REA.

Runs with kitty +runpy on a disposable Linux runner. Native decoded bytes and
wire replies are observations, not Nemoterm-generated expectations. No OS window
or GPU is created, and all generated image payloads are small fixture data.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import unittest
import zlib

UPSTREAM = '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(header, payload=b''):
    return b'\x1b_G' + header.encode('ascii') + b';' + base64.b64encode(payload) + b'\x1b\\'


def make_cases():
    """Return deterministic wire inputs independently of the native decoder."""
    width, height = 16, 8
    rgb = bytes((255, 0, 0, 0, 255, 0, 0, 0, 255, 32, 64, 128)) * 32
    rgba = bytes((255, 0, 0, 255, 0, 255, 0, 127, 0, 0, 255, 0, 32, 64, 128, 255)) * 32
    cases = []

    def add(name, steps):
        cases.append((name, steps))

    def header(fmt=32, **kw):
        fields = dict(a='t', i=1, f=fmt, s=width, v=height, o='z')
        fields.update(kw)
        return ','.join(f'{k}={v}' for k, v in fields.items())

    for fmt, raw in [(24, rgb), (32, rgba)]:
        for name, level, strategy, block_type in [('stored', 0, zlib.Z_DEFAULT_STRATEGY, 0),
                                                ('fixed', 6, zlib.Z_FIXED, 1),
                                                ('dynamic', 6, zlib.Z_HUFFMAN_ONLY, 2)]:
            encoder = zlib.compressobj(level, zlib.DEFLATED, 15, 8, strategy)
            packed = encoder.compress(raw) + encoder.flush()
            assert (packed[2] >> 1) & 3 == block_type
            assert zlib.decompress(packed) == raw
            add(f'{fmt}-{name}', [('load', command(header(fmt), packed))])

    packed = zlib.compress(rgba)
    add('three-chunks', [('first', command(header(m=1), packed[:1])),
                         ('middle', command('m=1', packed[1:-1])),
                         ('last', command('m=0', packed[-1:]))])
    add('empty-final-chunk', [('first', command(header(m=1), packed)),
                             ('last', command('m=0'))])
    add('query', [('query', command(header(a='q'), packed))])
    add('quiet-success', [('load', command(header(q=1), packed))])
    add('transmit-and-place', [('load', command(header(a='T', C=1), packed))])

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    scanlines = b''.join(b'\0' + rgba[y*width*4:(y+1)*width*4] for y in range(height))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))
    for name, size in [('exact-size', len(png)), ('short-size', len(png)-1),
                       ('long-size', len(png)+1), ('no-size', None)]:
        fields = 'a=t,i=1,f=100,o=z' + (f',S={size}' if size is not None else '')
        add('png-' + name, [('load', command(fields, zlib.compress(png)))])

    for name, data in [('checksum', packed[:-1] + bytes([packed[-1] ^ 1])),
                       ('truncated', packed[:-1]), ('raw-deflate', packed[2:-4]),
                       ('gzip', zlib.compress(rgba, wbits=31))]:
        add(name + '-and-recovery', [('load', command(header(), data)),
                                    ('recover', command(header(), packed))])
    add('trailing-bytes', [('load', command(header(), packed + b'end'))])
    add('concatenated-streams', [('load', command(header(), packed + zlib.compress(b'end')))])
    add('short-pixel-size', [('load', command(header(v=height-1), packed))])
    add('long-pixel-size', [('load', command(header(v=height+1), packed))])
    add('quiet-failure', [('load', command(header(q=2), packed[:-1]))])
    add('replace-with-compressed', [('plain', command('a=t,i=1,f=32,s=16,v=8', rgba[::-1])),
                                    ('replace', command(header(), packed))])
    add('cancel-pending', [('first', command(header(m=1), packed[:1])),
                           ('cancel', command('a=d,d=A')),
                           ('recover', command(header(), packed))])
    return cases


def main():
    import kitty.fast_data_types as native
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.graphics import TestGraphics
    from kitty_tests.main import env_for_python_tests

    output = Path(os.environ['NEMOTERM_KITTY_REFERENCE_OUTPUT']).resolve()
    source = Path(os.environ['NEMOTERM_KITTY_REFERENCE_SOURCE']).resolve()
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == UPSTREAM
    inputs = make_cases()
    record = dict(status='running', family='kitty-compression', upstream_commit=commit,
                  scope='Compiled upstream parser and decoded image bytes; no OS window or GPU pixels',
                  fixture_sha256=sha(Path(__file__).read_bytes()), platform=platform.platform(),
                  python=platform.python_version(), zlib_version=zlib.ZLIB_RUNTIME_VERSION,
                  source_sha256={p:sha((source/p).read_bytes()) for p in
                                 ('kitty/graphics.c', 'kitty_tests/graphics.py', 'docs/graphics-protocol.rst')},
                  compiled_sha256={p:sha((source/p).read_bytes()) for p in
                                   ('kitty/launcher/kitty', str(Path(native.__file__).relative_to(source)))},
                  expected_cases=[name for name, _ in inputs], cases=[])

    def save():
        output.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

    save()
    with env_for_python_tests():
        names = ('test_load_images', 'test_load_png')
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(TestGraphics(name) for name in names))
        record['upstream_tests'] = dict(names=list(names), run=result.testsRun,
                                       failures=len(result.failures), errors=len(result.errors),
                                       skipped=len(result.skipped), successful=result.wasSuccessful())
        save()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError('Upstream image loading tests did not all pass')

        for name, steps in inputs:
            helper = BaseTest()
            screen = helper.create_screen(12, 8, scrollback=20, cell_width=10, cell_height=20)
            case = dict(name=name, steps=[])
            record['cases'].append(case)
            try:
                for label, wire in steps:
                    screen.callbacks.clear()
                    parse_bytes(screen, wire)
                    count = screen.grman.image_count
                    # The upstream id lookup creates an empty image when the
                    # id is absent. Never call it on an empty manager, and do
                    # not request decoded data during a partial transmission.
                    pending = b'm=1' in wire.partition(b';')[0]
                    image, image_read_error = None, None
                    if count and not pending:
                        try:
                            image = screen.grman.image_for_client_id(1)
                        except RuntimeError as error:
                            # A rejected load can retain an internal slot with
                            # no decoded root frame. Preserve that observation
                            # and the wire reply instead of inventing pixels.
                            if str(error) != 'Failed to get data for root frame':
                                raise
                            image_read_error = str(error)
                    assert screen.grman.image_count == count
                    decoded = None
                    if image is not None:
                        raw = image['data']
                        decoded = {key:image[key] for key in ('client_id', 'width', 'height', 'is_4byte_aligned')}
                        decoded.update(data_base64=base64.b64encode(raw).decode('ascii'),
                                       data_sha256=sha(raw), data_bytes=len(raw))
                    case['steps'].append(dict(label=label, input_base64=base64.b64encode(wire).decode('ascii'),
                                             reply_base64=base64.b64encode(screen.callbacks.wtcbuf).decode('ascii'),
                                             cursor=[screen.cursor.x, screen.cursor.y],
                                             image_count=count, partial_transfer=pending, image=decoded,
                                             image_read_error=image_read_error))
                    save()
                print('Captured compression:', name, len(steps), 'states', flush=True)
            finally:
                screen.reset()
                helper.tearDown()

    record.update(status='complete', case_count=len(record['cases']),
                  state_count=sum(len(c['steps']) for c in record['cases']))
    save()
    print('Completed compression reference:', record['case_count'], record['state_count'], flush=True)


if __name__ == '__main__':
    main()
