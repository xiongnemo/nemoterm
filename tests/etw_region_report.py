"""Correlate retained VM events and stacks by exact QPC/PID/thread identity.

Offline evidence analysis only: never launches or attaches to a process.
Module attribution uses a preceding load/rundown and respects unloads.
Unmatched events and unknown addresses remain explicit.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_key(event):
    data = event['data']
    return (event['info']['Opcode'], *(int(data[k], 0) for k in
            ('BaseAddress', 'RegionSize', 'ProcessId', 'Flags')))


def report(source, replay):
    pid = source['pid']
    assert pid == replay['pid']
    assert source['stack_decode_error_count'] == 0
    assert source['headers']
    for header in source['headers']:
        data = header['data']
        assert int(data['PointerSize']) == 8
        assert int(data['EventsLost']) == int(data['BuffersLost']) == 0
    start, end = (int(replay['region'][k], 0) for k in ('start', 'end'))
    events = [e for e in source['events']
              if start <= int(e['data']['BaseAddress'], 0) < end]
    assert all(int(e['data']['ProcessId']) == pid for e in events)
    assert [event_key(e) for e in events] == [event_key(e) for e in replay['events']]
    assert all(int(a['time']['RawTime']) <= int(b['time']['RawTime'])
               for a, b in zip(events, events[1:]))
    stacks = defaultdict(list)
    for stack in source['stacks']:
        assert stack['pid'] == pid
        stacks[(stack['qpc'], stack['thread'])].append(stack)
    images = sorted(source['images'], key=lambda i: int(i['time']['RawTime']))
    used_images = set()

    def resolve(address, timestamp):
        value, match = int(address, 0), None
        for index, image in enumerate(images):
            if int(image['time']['RawTime']) > timestamp:
                break
            data = image['data']
            base, size = int(data['ImageBase'], 0), int(data['ImageSize'], 0)
            if base <= value < base + size:
                op = image['info']['Opcode']
                if op in ('Load', 'DCStart'):
                    match = index
                elif op == 'UnLoad':
                    match = None
        if match is None:
            return dict(address=address, module=None, offset=None, image=None)
        used_images.add(match)
        data = images[match]['data']
        return dict(address=address, module=data['FileName'].split('\\')[-1],
                    offset=hex(value-int(data['ImageBase'], 0)), image=match)

    patterns, pattern_ids, matches = [], {}, []
    counts, paths = Counter(), Counter()
    for index, event in enumerate(events):
        qpc, thread = int(event['time']['RawTime']), int(event['execution']['ThreadID'])
        matched = stacks[(qpc, thread)]
        counts[(event['info']['Opcode'], event['data']['Flags'], len(matched))] += 1
        records = []
        for stack in matched:
            if stack['raw_payload']:
                raw = bytes.fromhex(stack['raw_payload'])
                assert struct.unpack_from('<QII', raw) == (qpc, pid, thread)
                assert [hex(v[0]) for v in struct.iter_unpack('<Q', raw[16:])] == stack['frames']
            frames = [resolve(a, qpc) for a in stack['frames']]
            key = tuple((f['address'], f['image']) for f in frames)
            if key not in pattern_ids:
                pattern_ids[key] = len(patterns)
                patterns.append(frames)
            records.append(dict(qpc=qpc, pid=pid, thread=thread,
                                pattern=pattern_ids[key], raw_payload=stack['raw_payload'],
                                decoded_data=stack['decoded_data']))
            calls = [f['offset'] for f in frames if (f['module'] or '').lower() == 'nemoterm.exe']
            paths[(event['info']['Opcode'], event['data']['Flags'], tuple(calls[:2]))] += 1
        matches.append(dict(event=index, stacks=records))
    pages, growth = set(), Counter()
    before = replay['replay']['observe-workload']['event_count']
    after = replay['replay']['after-workload']['event_count']
    for index, event in enumerate(events):
        data = event['data']
        base, size, flags = (int(data[k], 0) for k in ('BaseAddress', 'RegionSize', 'Flags'))
        touched = set(range(base//4096, (base+size+4095)//4096))
        if flags & 0x1000:
            new = touched-pages
            pages.update(touched)
            if before <= index < after:
                records = matches[index]['stacks']
                assert len(records) == 1, 'Ambiguous allocation growth attribution'
                frames = patterns[records[0]['pattern']]
                calls = tuple(f['offset'] for f in frames
                              if (f['module'] or '').lower() == 'nemoterm.exe')
                growth[calls[:2]] += len(new)*4096
        elif flags & 0x4000:
            pages.difference_update(touched)
        elif flags & 0x8000:
            assert base == start
            pages.clear()
        if index+1 in (before, after):
            expected = replay['region']['before_committed_bytes' if index+1 == before else 'after_committed_bytes']
            assert len(pages)*4096 == expected
    assert not pages, 'Reservation was not released'
    return dict(pid=pid, executable_sha256=source['metadata_image_sha256'],
                memory_acceptance=False, matching='exact original QPC, owned PID and thread',
                region=replay['region'], replay=replay['replay'], events=events,
                matches=matches, stack_patterns=patterns,
                images={str(i): images[i] for i in sorted(used_images)},
                coverage=[dict(opcode=k[0], flags=k[1], matching_stacks=k[2], events=v)
                          for k, v in counts.items()],
                application_paths=[dict(opcode=k[0], flags=k[1], return_rvas=k[2], events=v)
                                   for k, v in paths.most_common()],
                workload_new_committed_pages=[dict(return_rvas=k, bytes=v) for k, v in growth.most_common()],
                limitations=['Free events without exact stacks are not assigned a caller.',
                             'Module offsets do not provide private symbol names.',
                             'This trace used a hosted runner, not the local GPU.',
                             'Commitment, private residency and live resource bytes differ.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = report(json.loads(args.source.read_text(encoding='utf-8')),
                    json.loads(args.replay.read_text(encoding='utf-8')))
    result['source_sha256'] = digest(args.source)
    result['replay_sha256'] = digest(args.replay)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('pid', 'coverage', 'application_paths')}, indent=2))


if __name__ == '__main__':
    main()
