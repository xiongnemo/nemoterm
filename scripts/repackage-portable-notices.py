"""Complete notices on a hosted runner without rebuilding or running binaries."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import subprocess
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise SystemExit('Packaging replay requires a GitHub-hosted runner')
    run_id, commit = os.environ['SOURCE_RUN'], os.environ['SOURCE_COMMIT']
    assert re.fullmatch(r'\d+', run_id) and re.fullmatch(r'[0-9a-f]{40}', commit)
    repository = os.environ['GITHUB_REPOSITORY']
    assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
    root = Path(__file__).resolve().parents[1]
    destination = root/'build/portable-notices'
    destination.mkdir(parents=True)

    def api(name, endpoint):
        raw = subprocess.check_output(['gh','api',f'repos/{repository}/actions/{endpoint}'])
        (destination/(name+'.json')).write_bytes(raw)
        return json.loads(raw)

    run = api('source-run',f'runs/{run_id}')
    jobs = api('source-jobs',f'runs/{run_id}/jobs?per_page=100')['jobs']
    assert run['status']=='completed' and run['head_sha']==commit
    for job_name in ('Windows x64 tests and portable build',
                     'Source-built console host for compiler comparison'):
        passed = [j for j in jobs if j['name']==job_name and j['conclusion']=='success']
        assert len(passed)==1, job_name
    subprocess.run(['git','diff','--exit-code',commit,'HEAD','--','vendor','native','locales',
        'scripts/build.ps1','scripts/build-single-exe.ps1','scripts/prepare-single-exe.py',
        'scripts/generate-ui-catalog.py'],cwd=root,check=True)
    artifacts = api('source-artifacts',f'runs/{run_id}/artifacts?per_page=100')['artifacts']
    candidates = [a for a in artifacts if a['name']=='nemoterm-windows-x64-'+commit]
    assert len(candidates)==1 and not candidates[0]['expired']
    artifact = candidates[0]
    original = destination/'original.zip'
    with original.open('wb') as stream:
        subprocess.run(['gh','api',f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip'],
                       stdout=stream,check=True)
    package = destination/'package'
    package.mkdir()
    original_files = {}
    with zipfile.ZipFile(original) as bundle:
        assert bundle.testzip() is None
        for member in bundle.infolist():
            name = PurePosixPath(member.filename)
            assert len(name.parts)==1 and not name.is_absolute() and name.name not in ('.','..')
            assert '\\' not in member.filename and not member.is_dir()
            assert name.name not in original_files
            data = bundle.read(member)
            (package/name.name).write_bytes(data)
            original_files[name.name] = dict(bytes=len(data),sha256=digest(data))
    assert {'nemoterm.exe','OpenConsole.exe','conpty.dll','SHA256SUMS.txt','SOURCE-HOST.json'} <= original_files.keys()
    sums = (package/'SHA256SUMS.txt').read_text().splitlines()
    # GNU sha256sum uses a leading '*' for a file read in binary mode.
    frontend = [match.group(1) for line in sums
                if (match := re.fullmatch(r'([0-9a-f]{64}) [ *]nemoterm\.exe', line))]
    assert frontend == [original_files['nemoterm.exe']['sha256']], 'Frontend checksum mismatch'
    host = json.loads((package/'SOURCE-HOST.json').read_text(encoding='utf-8-sig'))
    assert host['SourceCommit']==commit
    assert host['Executable']['SHA256']==original_files['OpenConsole.exe']['sha256']
    additions = {}
    for source, name in [('vendor/terminfo/COPYING.ncurses','LICENSE-Ncurses.txt'),
                         ('tools/x11/xorg-server-21.1.16/LICENSE.txt','LICENSE-X11-Colours.txt')]:
        data = (root/source).read_bytes()
        if name in original_files:
            assert original_files[name]['sha256']==digest(data), 'Existing notice differs'
        (package/name).write_bytes(data)
        additions[name] = dict(source=source,bytes=len(data),sha256=digest(data))
    for name, identity in original_files.items():
        assert digest((package/name).read_bytes()) == identity['sha256'], name
    record = dict(scope='Notice-only packaging replay; original files remain byte-identical.',
        source_run=run_id,source_commit=commit,source_artifact_id=artifact['id'],
        source_zip_sha256=digest(original.read_bytes()),
        fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        original_files=original_files,notices=additions,all_original_files_unchanged=True)
    text = json.dumps(record,indent=2)+'\n'
    (destination/'verification.json').write_text(text)
    (package/'PACKAGING-REPLAY.json').write_text(text)
    print('Preserved',len(original_files),'original files; completed',len(additions),'notice files.')
    print('Frontend SHA256:',original_files['nemoterm.exe']['sha256'])


if __name__ == '__main__':
    main()
