"""Read the original Windows interaction-agents ZIP. Never runs a terminal or a client.

Report the first marked request and any subsequent images separately for both
shortcuts, input paths and startup phases. Exit nonzero for a failed case or
missing/incorrect first image, including in the early-input group.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


IDLE = b'\x1b]7501;state=idle:app=codex'
BINDINGS = {'ctrl-v', 'ctrl-shift-v'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def review(path, expected_commit):
    with ZipFile(path) as archive:
        def read(name):
            return json.loads(archive.read(name).decode('utf-8-sig'))

        source = read('interaction-product/SOURCE-HOST.json')
        identity = read('interaction/identity.json')
        product = source['Executable']; client = identity['clients']['codex']['sha256']
        require(source['SourceCommit'] == expected_commit and not identity['fixture_dirty'] and
                product == {'SHA256': identity['executable_sha256'], 'Bytes': identity['executable_bytes']}, 'product or fixture identity mismatch')
        results = read('interaction/results.json')
        output = {}
        for ready in (False, True):
            for system in (False, True):
                case = 'agent-image' + ('-ready' if ready else '') + ('-system' if system else '') + '-codex'
                [row] = [r for r in results if r['id'] == case]
                prefix = 'interaction/' + row['directory'] + '/'
                def original(name):
                    blob = archive.read(prefix + name)
                    require(sha256(blob).hexdigest() == row['evidence'][name], 'evidence digest mismatch: '+name)
                    return blob

                sessions = {}
                for name in row['evidence']:
                    if not name.endswith('/observed.json'): continue
                    folder = PurePosixPath(name).parent; binding = folder.name
                    require(binding in BINDINGS and binding not in sessions, 'duplicate or unexpected binding: '+name)
                    obs = json.loads(original(name)); at = json.loads(original(str(folder/'at-paste.json')))
                    trace = original(str(folder/'at-paste.vt')); marker = 'NEMOTERM_CODEX_IMAGE_' + binding.upper().replace('-', '_')
                    require(obs['terminal_sha256'] == product['SHA256'] and obs['client_sha256'] == client and obs['client']=='codex' and
                            obs['generated_bitmap'] == [32,16] and at['marker'] == marker and at['binding'] == binding and at['system'] == system and
                            at['bytes'] == len(trace) and at['sha256'] == sha256(trace).hexdigest() and at['idle_before'] == (IDLE in trace), 'inconsistent at-paste observation: ' + name)
                    if ready:
                        proof = json.loads(original(str(folder/'idle-redraw.json')))
                        require(at['idle_before'] and trace[proof['idle_offset']:].startswith(IDLE), 'missing client idle marker: '+name)
                    marked = [r for r in obs['requests'] if r['path']=='/v1/responses' and marker in r['text']]
                    images = [r['images'] for r in marked]
                    first = images[0] if images else []
                    exact = (len(first)==1 and first[0].get('generated_pixels_match') is True and
                             first[0]['mime']=='image/png' and first[0]['png_size']==[32,16])
                    result = ('no-marked-request' if not marked else 'text-only' if not first else
                              'exact-image' if exact else 'unexpected-image')
                    sessions[binding] = dict(first_submission=result, images_per_marked_request=[len(r) for r in images],
                        first_image_sha256=[im['sha256'] for im in first], idle_before=at['idle_before'],
                        clipboard_restored=obs['clipboard_restored'], passed=bool(exact and not any(images[1:]) and obs['clipboard_restored']))
                require(set(sessions)==BINDINGS, 'missing observations: '+case)
                output[case] = dict(fixture_status=row['status'], input='physical' if system else 'window API',
                                    phase='after idle redraw' if ready else 'first visible input', shortcuts=sessions)
        return dict(product=expected_commit, executable=product, client=client, fixture_commit=identity['fixture_commit'],
                    artifact_sha256=sha256(path.read_bytes()).hexdigest(), cases=output)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path)
    parser.add_argument('--expect-commit',required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=review(args.archive,args.expect_commit);text=json.dumps(report,indent=2)
    if args.output: args.output.write_text(text+'\n', encoding='utf8')
    else: print(text)
    raise SystemExit(any(c['fixture_status']!='passed' or not all(s['passed'] for s in c['shortcuts'].values()) for c in report['cases'].values()))
