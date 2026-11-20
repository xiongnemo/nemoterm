"""Fetch the four immutable archives used by review-frontend-memory.py."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile


def fetch(run, commit, output):
    if run < 1 or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected a source run ID and a full Git commit')
    api = 'repos/' + os.environ['GITHUB_REPOSITORY'] + '/actions/'
    def get(path):
        return subprocess.check_output(['gh', 'api', api + path])
    record = json.loads(get(f'runs/{run}'))
    if record['head_sha'] != commit or record['path'] != '.github/workflows/ci.yml':
        raise ValueError('Expected ci.yml for the requested product commit')
    suffix = f"-{run}-{record['run_attempt']}"
    names = {'source': 'source-console-host-x64-' + commit, 'conversation': 'agent-session-memory' + suffix,
             'gdi': 'interaction-receipt-memory-gdi' + suffix, 'directx': 'interaction-receipt-memory-directx' + suffix}
    pages = json.loads(subprocess.check_output(['gh', 'api', '--paginate', '--slurp', api + f'runs/{run}/artifacts?per_page=100']))
    available = [a for page in pages for a in page['artifacts']]
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'source_run': run, 'source_commit': commit, 'attempt': record['run_attempt'], 'archives': {}}
    try:
        for key, name in names.items():
            matches = [a for a in available if a['name'] == name]
            if len(matches) != 1: raise ValueError(f'{name}: expected one archive, found {len(matches)}')
            a = matches[0]
            if a['expired'] or (a['workflow_run']['id'], a['workflow_run']['head_sha']) != (run, commit):
                raise ValueError(f'{name}: expired or wrong product')
            data = get(f"artifacts/{a['id']}/zip")
            if len(data) != a['size_in_bytes'] or 'sha256:' + sha256(data).hexdigest() != a['digest']:
                raise ValueError(f'{name}: downloaded archive differs from GitHub digest')
            path = output / (key + '.zip'); path.write_bytes(data)
            receipt['archives'][key] = {field:a[field] for field in ('id','name','digest','size_in_bytes')}
            if key == 'source':
                with ZipFile(path) as z:
                    manifest = json.loads(z.read('SOURCE-HOST.json').decode('utf-8-sig')); exe = z.read('nemoterm.exe')
                if manifest['SourceCommit'] != commit or manifest['Executable'] != {'Bytes':len(exe),'SHA256':sha256(exe).hexdigest()}:
                    raise ValueError('Source executable does not match its manifest')
                receipt['executable'] = manifest['Executable']
    finally:
        (output/'inputs.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=int); parser.add_argument('commit'); parser.add_argument('output',type=Path)
    args=parser.parse_args(); fetch(args.run,args.commit,args.output)
