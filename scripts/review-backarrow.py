"""Compare the original Windows child input against two independently captured XTerm installations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ACK = b'\x1b[0n'
QUERY = re.compile(rb'\x1b\[\?67;([0-4])\$y\x1bP1\+r6b6273=([0-9a-fA-F]{2})\x1b\\')
PROFILES = {'default-bs', 'default-del', 'tcap-bs', 'tcap-del'}


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def fields(raw):
    m = QUERY.fullmatch(raw)
    if m is None:
        return None
    return int(m[1]), int(m[2], 16)


def source(kind):
    path = ROOT/'testdata/upstream'/('backarrow-xterm'+('-pinned' if kind=='bundled' else '')+'.zip')
    with zipfile.ZipFile(path) as z:
        r = json.loads(z.read('backarrow.json'))
        info = dict(archive_sha256=digest(path.read_bytes()), xterm_commit=z.read('upstream-commit.txt').decode().strip(),
                    fixture_commit=z.read('fixture-commit.txt').decode().strip(), xterm_sha256=r['executable_sha256'],
                    xterm_version=z.read('version.txt').decode().strip())
        assert info['xterm_sha256'] == z.read('executable-sha256.txt').decode().split()[0]
        if kind == 'bundled':
            manifest=json.loads((ROOT/'vendor/terminfo/manifest.json').read_bytes())
            info['database_source_sha256']=z.read('pinned-terminfo-sha256.txt').decode().split()[0]
            info['ncurses_commit']=z.read('ncurses-commit.txt').decode().strip()
            assert (info['database_source_sha256'],info['ncurses_commit']) == (manifest['source_sha256'],manifest['ncurses_commit'])
            assert info['xterm_commit']==manifest['xterm_commit']
    assert r['completed'] and set(r['cases'])==PROFILES
    return info, r['cases']


def compare(record, product_hash):
    assert record['completed'] and record['exe_sha256']==product_hash and set(record['cases'])==PROFILES
    result=dict(executable_sha256=product_hash, native_fixture=record.get('fixture_commit'), font=record['font'], references={})
    for kind in ('distribution','bundled'):
        src, ref=source(kind)
        rows={}; counts=dict(raw=0,mode=0,kbs=0,key=0,all_fields_and_key=0)
        for name in sorted(PROFILES):
            actual=record['cases'][name]; expected=ref[name]
            assert actual['exit_code']==expected['exit_code']==0 and actual['renderer']==1 and expected['completed']
            assert not actual['cleanup']['terminated_remaining'] and actual['settings']['BackspaceIsDelete']==int(name.endswith('-del'))
            assert len(actual['steps'])==len(expected['steps'])==16
            for a,e in zip(actual['steps'],expected['steps']):
                label=name+'/'+a['label']; assert label not in rows
                assert (a['sequence_hex'],a['label'],a['actions'])==(e['sequence_hex'],e['label'],e['actions'])
                aq,with_z,tail=bytes.fromhex(a['wire_with_sentinel_and_barriers_hex']).split(ACK)
                eq,ek,et=bytes.fromhex(e['wire_with_barriers_hex']).split(ACK)
                assert tail==et==b'' and with_z.endswith(b'z') and eq+ek==bytes.fromhex(e['reply_hex'])
                ak=with_z[:-1]; af=fields(aq); ef=fields(eq); assert ef is not None
                assert a['actual_key']==ak.hex() and a['actual_query']==aq.hex()
                matches=dict(raw=aq==eq and ak==ek,mode=bool(af and af[0]==ef[0]),kbs=bool(af and af[1]==ef[1]),
                             key=ak==ek,all_fields_and_key=af==ef and ak==ek)
                rows[label]=dict(windows_query=aq.hex(),xterm_query=eq.hex(),windows_key=ak.hex(),xterm_key=ek.hex(),matches=matches)
                for field in counts: counts[field]+=int(matches[field])
        result['references'][kind]=dict(identity=src,counts=counts,rows=rows)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);p.add_argument('manifest',type=Path)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.receipt.read_bytes(); manifest=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    result=compare(json.loads(raw),manifest['Executable']['SHA256']); result.update(receipt_sha256=digest(raw),product_commit=manifest['SourceCommit'])
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    for k,r in result['references'].items(): print(k,r['counts'])
    # This is an additional matched-database check. The existing byte-for-byte
    # comparison against distribution XTerm still runs and retains its verdict.
    return int(result['references']['bundled']['counts']['all_fields_and_key']!=64)


if __name__ == '__main__':
    raise SystemExit(main())
