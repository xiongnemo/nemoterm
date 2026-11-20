"""Download and authenticate two saved interaction archives and the executable that produced them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile


def fetch(product_run, commit, receipt_run, output):
    output.mkdir(parents=True,exist_ok=False)
    base='repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/'
    def api(s):return subprocess.check_output(['gh','api',base+s])
    meta=json.loads(api(f'runs/{product_run}'));assert meta['head_sha']==commit
    trace=json.loads(api(f'runs/{receipt_run}')); ids={}
    def download(run,name,dest):
        rows=[];page=1
        while True:
            part=json.loads(api(f'runs/{run}/artifacts?per_page=100&page={page}'))['artifacts'];rows.extend(a for a in part if a['name']==name)
            if len(part)<100:break
            page+=1
        a,=rows;assert not a['expired'];blob=api(f'artifacts/{a["id"]}/zip');assert len(blob)==a['size_in_bytes'] and 'sha256:'+hashlib.sha256(blob).hexdigest()==a['digest']
        ids[dest]=dict(run=run,name=name,id=a['id'],digest=a['digest']);p=output/dest;p.write_bytes(blob);return p
    with ZipFile(download(product_run,'source-console-host-x64-'+commit,'source.zip')) as z:
        manifest=json.loads(z.read('SOURCE-HOST.json').decode('utf-8-sig'));binary=z.read('nemoterm.exe')
        assert manifest['SourceCommit']==commit and manifest['Executable']==dict(Bytes=len(binary),SHA256=hashlib.sha256(binary).hexdigest())
    suffix=f'agents-grid-{receipt_run}-{trace["run_attempt"]}'
    for prefix,dest in [('interaction-receipt-','receipt.zip'),('interaction-','surfaces.zip')]:
        with ZipFile(download(receipt_run,prefix+suffix,dest)) as z:
            assert json.loads(z.read('interaction-product/SOURCE-HOST.json').decode('utf-8-sig'))==manifest
            identity=json.loads(z.read('interaction/identity.json'));assert identity['fixture_commit']==trace['head_sha'] and identity['executable_sha256']==manifest['Executable']['SHA256']
    (output/'inputs.json').write_text(json.dumps(ids,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('product_run',type=int);p.add_argument('commit');p.add_argument('receipt_run',type=int);p.add_argument('output',type=Path);args=p.parse_args();fetch(args.product_run,args.commit,args.receipt_run,args.output)
