"""Retain the original XTerm frames for cold shared, private and post-reset Sixel registers."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
from PIL import Image


def digest(data): return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('sha256');p.add_argument('output',type=Path)
    p.add_argument('--artifact',required=True,type=int);p.add_argument('--run',required=True,type=int)
    args=p.parse_args();raw=args.archive.read_bytes();assert digest(raw)==args.sha256
    summary={}; retained={}
    with ZipFile(io.BytesIO(raw)) as z:
        facts=json.loads(z.read('observations.json'))
        assert facts['completed'] and facts['repaint'] and not facts['control_failures'] and not facts['transport_mismatches']
        targets=[tag for tag in facts['cases'] if tag.startswith('bank-start-')]; assert len(targets)==7
        for tag in sorted(targets):
            summary[tag]={}
            for tx in ('whole','bytewise'):
                obs=facts['cases'][tag][tx]; assert obs['completed'] and not obs['forced_cleanup'] and obs['cell_pixels']==[6,13]
                step,=obs['steps']; prefix='observations/'+tag+'-'+tx+'/'
                assert step['repaint_barrier_hex']=='1b5b306e'
                summary[tag][tx]={}
                for name,rec in [('initial',obs['initial_frame']),('frame',step['frame']),('repaint',step['repaint'])]:
                    f=prefix+rec['file'];data=z.read(f);retained[f]=data
                    image=Image.open(io.BytesIO(data)).convert('RGB');assert digest(image.tobytes())==rec['rgb_sha256']
                    summary[tag][tx][name]=[sorted([n,bytes(col).hex()] for n,col in image.crop((2+x,2,2+x+4,8)).getcolors()) for x in (0,4,8,12)]
                for f in ('control.json','child.json','observed.json'): retained[prefix+f]=z.read(prefix+f)
            assert summary[tag]['whole']==summary[tag]['bytewise']
        for f in ('observations.json','source-executable-sha256.txt','version.txt'):retained[f]=z.read(f)
    meta=dict(run=args.run,artifact=args.artifact,archive_sha256=args.sha256,files={f:digest(v) for f,v in sorted(retained.items())},stripes=summary)
    with ZipFile(args.output,'x') as out:
        for f,data in sorted(retained.items()):out.writestr(ZipInfo('reference/'+f),data,compress_type=ZIP_DEFLATED)
        out.writestr(ZipInfo('source.json'),json.dumps(meta,sort_keys=True,indent=2),compress_type=ZIP_DEFLATED)
    print(digest(args.output.read_bytes()),args.output)
    for tag,v in summary.items():print(tag,v['whole']['frame'],v['whole']['repaint'])

if __name__=='__main__':main()
