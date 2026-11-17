"""Compare the native component with unchanged hosted XTerm bytes and pixels.

This is not the terminal's DCS parser, Windows rendering or lifecycle test.
Unsupported stream kinds are explicitly excluded from this component stage.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
from PIL import Image


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Run component checks on a GitHub-hosted runner')
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--font-inputs',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile('research/regis-reference-evidence.zip') as outer:
        original=outer.read('44093439244/14331564743.zip')
    assert hashlib.sha256(original).hexdigest()=='f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00'
    evidence=dict(scope=__doc__,executable_sha256=hashlib.sha256(args.exe.read_bytes()).hexdigest(),
                  fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  cases={},excluded={},failures=[],completed=False)
    command=[str(args.exe.resolve())]
    if args.font_inputs:
        command+=['--font-inputs',str(args.font_inputs.resolve())]
        evidence['font_inputs_sha256']=hashlib.sha256(args.font_inputs.read_bytes()).hexdigest()
        evidence['font_scope']='Pinned upstream Xft input masks; not the Windows native font provider.'
    pattern=rb'(?:\x1b\[\?1070([hl]))?\x1bP([0-9]+)p([^\x1b]*)\x1b\\'
    with zipfile.ZipFile(io.BytesIO(original)) as bundle:
        observed=json.loads(bundle.read('observations.json'))
        for name,variants in observed['cases'].items():
            steps=variants['whole']['steps']
            matches=[re.fullmatch(pattern,bytes.fromhex(s['sequence_hex'])) for s in steps]
            if not all(matches):
                evidence['excluded'][name]='Requires terminal CSI/Sixel/cancellation integration; original stream retained unchanged.'
                continue
            wire=b''
            for match in matches:
                if match[1]: wire+=b'C '+(b'1' if match[1]==b'h' else b'0')+b'\n'
                body=match[3]
                wire+=b'P '+match[2]+b' '+str(len(body)).encode()+b'\n'+body
            process=subprocess.run(command,input=wire,capture_output=True,timeout=30)
            record=dict(exit_code=process.returncode,stderr=process.stderr.decode(errors='replace'),steps=[])
            evidence['cases'][name]=record
            if process.returncode:
                evidence['failures'].append(dict(case=name,kind='process',code=process.returncode))
                continue
            output=io.BytesIO(process.stdout)
            for index,step in enumerate(steps):
                status,memory,page,width,height,reply_length=map(int,output.readline().split())
                reply=output.read(reply_length)
                pixels=output.read(160*120*3)
                source_name=f'observations/{name}-whole/{step["frame"]["file"]}'
                image=Image.open(io.BytesIO(bundle.read(source_name))).convert('RGB')
                expected=image.crop((2,2,162,122)).tobytes()
                mismatches=sum(pixels[i:i+3]!=expected[i:i+3] for i in range(0,len(expected),3))
                item=dict(status=status,memory_bytes=memory,page=page,width=width,height=height,
                          reply_hex=reply.hex(),expected_reply_hex=step['reply_hex'],
                          rgb_sha256=hashlib.sha256(pixels).hexdigest(),
                          reference_crop_sha256=hashlib.sha256(expected).hexdigest(),pixel_mismatches=mismatches)
                record['steps'].append(item)
                if status or reply.hex()!=step['reply_hex'] or mismatches:
                    evidence['failures'].append(dict(case=name,step=index,**item))
                    if len(pixels)==160*120*3:
                        Image.frombytes('RGB',(160,120),pixels).save(args.output/f'{name}-{index}-actual.png')
                    image.crop((2,2,162,122)).save(args.output/f'{name}-{index}-reference.png')
            assert output.read()==b'',name
    evidence['completed']=True
    (args.output/'observations.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(evidence['cases']),excluded=len(evidence['excluded']),failures=evidence['failures']),indent=2))
    if evidence['failures']: raise SystemExit(1)


if __name__=='__main__': main()
