"""Compare ReGIS decoder pixels with unchanged hosted XTerm bytes and pixels.

Terminal mode exercises the real DCS parser. View mode also composites the
retained images through the same row accessors used by the Windows frontend,
covering graphics lifecycle. This is not a native window screenshot check.
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
    parser.add_argument('--grid-font',type=Path)
    parser.add_argument('--terminal',action='store_true',help='Feed original DCS/CSI bytes through terminal.c')
    parser.add_argument('--bytewise',action='store_true')
    parser.add_argument('--views',action='store_true',help='Compare actual retained image views, including lifecycle and Sixel')
    parser.add_argument('--shared-palette',action='store_true',
                        help='Additional two-way palette scenes against separately retained XTerm full repaints')
    parser.add_argument('--register-readback',action='store_true',
                        help='Compare four fresh Sixel register readbacks against pinned XTerm repaints')
    parser.add_argument('--private-registers',action='store_true',
                        help='Compare both stages of four private Sixel register scenes with original XTerm')
    args=parser.parse_args()
    register_scenes=args.register_readback or args.private_registers
    assert sum((args.shared_palette,args.register_readback,args.private_registers))<=1
    args.output.mkdir(parents=True,exist_ok=True)
    if args.private_registers:
        assert args.terminal and args.views
        original=Path('research/private-sixel-terminator-xterm.zip').read_bytes()
        assert hashlib.sha256(original).hexdigest()=='43325228851c7292d71a3dc846f64e8cacaef99ef98b394a5ecc5016cee91b4c'
    elif args.register_readback:
        assert args.terminal and args.views and not args.shared_palette
        original=Path('research/shared-register-readback-xterm.zip').read_bytes()
        assert hashlib.sha256(original).hexdigest()=='193fc60e26d512680bf3bd357bcaf0da2a1b0c85323b7d92ae834f12e7840255'
    elif args.shared_palette:
        assert args.terminal and args.views
        original=Path('research/regis-repaint-reference.zip').read_bytes()
        assert hashlib.sha256(original).hexdigest()=='ca9165f9d14cb8ef67840a3c46063fde3d4f9dc104ac58086bc9b125c79fac4f'
    else:
        with zipfile.ZipFile('research/regis-reference-evidence.zip') as outer:
            original=outer.read('44093439244/14331564743.zip')
        assert hashlib.sha256(original).hexdigest()=='f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00'
    evidence=dict(scope=__doc__,executable_sha256=hashlib.sha256(args.exe.read_bytes()).hexdigest(),
                  fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  cases={},excluded={},failures=[],completed=False)
    evidence['reference_archive_sha256']=hashlib.sha256(original).hexdigest()
    evidence['reference_frame']='repaint' if args.shared_palette or register_scenes else 'frame'
    command=[str(args.exe.resolve())]
    evidence['terminal_parser']=args.terminal
    evidence['image_views']=args.views
    evidence['transport']='bytewise' if args.bytewise else 'whole'
    if args.bytewise:
        assert args.terminal,'bytewise applies to the real terminal parser'
        command+=['--bytewise']
    if args.views:
        assert args.terminal
        command+=['--views']
    if args.grid_font:
        command+=['--grid-font',str(args.grid_font.resolve())]
        evidence['grid_font_sha256']=hashlib.sha256(args.grid_font.read_bytes()).hexdigest()
    if args.font_inputs:
        command+=['--font-inputs',str(args.font_inputs.resolve())]
        evidence['font_inputs_sha256']=hashlib.sha256(args.font_inputs.read_bytes()).hexdigest()
        evidence['font_scope']='Pinned upstream Xft input masks; not the Windows native font provider.'
    pattern=rb'(?:\x1b\[\?1070([hl]))?\x1bP([0-9]+)p([^\x1b]*)\x1b\\'
    with zipfile.ZipFile(io.BytesIO(original)) as bundle:
        observed=json.loads(bundle.read('observations.json'))
        if args.shared_palette:
            assert observed['completed'] and not observed['transport_mismatches'] and not observed['control_failures']
            assert {'shared-palette-sixel-terminated','shared-palette-regis-recolour'}<=observed['cases'].keys()
        if register_scenes:
            family,prefixes=(('private-register-',('identity','overwrite')) if args.private_registers
                             else ('shared-register-readback-',('empty','painted')))
            readbacks={family+prefix+'-'+end for prefix in prefixes for end in ('st','dollar')}
            assert observed['completed'] and not observed['transport_mismatches'] and not observed['control_failures']
            assert readbacks <= observed['cases'].keys()
        reference_transport=evidence['transport'] if register_scenes else 'whole'
        for name,variants in observed['cases'].items():
            if register_scenes and name not in readbacks:
                evidence['excluded'][name]='Outside the four selected register scenes.'
                continue
            if args.shared_palette and not name.startswith('shared-palette-'):
                evidence['excluded'][name]='Outside the additional two-way shared-palette comparison; original gates remain separate.'
                continue
            steps=variants[reference_transport]['steps']
            if register_scenes:
                assert variants[reference_transport]['completed'] and len(steps)==(2 if args.private_registers else 3)
            matches=[re.fullmatch(pattern,bytes.fromhex(s['sequence_hex'])) for s in steps]
            if args.views and name=='control-capability':
                evidence['excluded'][name]='Terminal identity control; ReGIS capability is not advertised yet.'
                continue
            if not args.views and not all(matches):
                evidence['excluded'][name]='Requires terminal CSI/Sixel/cancellation integration; original stream retained unchanged.'
                continue
            wire=b''
            for match,step in zip(matches,steps):
                if args.terminal:
                    original_wire=bytes.fromhex(step['sequence_hex'])
                    wire+=b'I '+str(len(original_wire)).encode()+b'\n'+original_wire
                    continue
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
                reference_frame=step[evidence['reference_frame']]
                source_name=f'observations/{name}-{reference_transport}/{reference_frame["file"]}'
                image=Image.open(io.BytesIO(bundle.read(source_name))).convert('RGB')
                expected=image.crop((2,2,162,122)).tobytes()
                mismatches=sum(pixels[i:i+3]!=expected[i:i+3] for i in range(0,len(expected),3))
                item=dict(status=status,memory_bytes=memory,page=page,width=width,height=height,
                          reply_hex=reply.hex(),expected_reply_hex=step['reply_hex'],
                          rgb_sha256=hashlib.sha256(pixels).hexdigest(),
                          reference_frame_file=reference_frame['file'],
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
