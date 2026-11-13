"""Extract one owned PID's VM events/stacks from tracerpt -rts XML.

StackWalk opcode 32 layout follows Microsoft's StackWalk_Event definition:
QPC timestamp, uint32 PID/TID, then pointer-width instruction addresses.
This is metadata decoding, not application execution or memory acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--metadata',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
metadata=json.loads(args.metadata.read_text(encoding='utf-8'))
pid=metadata['pid']
ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event',
    't':'http://schemas.microsoft.com/win/2004/08/events/trace'}
parse=ET.iterparse(args.input,events=('start','end'));_,root=next(parse)
result=dict(pid=pid,memory_acceptance=False,events=[],stacks=[],images=[],headers=[],
    source_xml_bytes=args.input.stat().st_size,metadata_sha256=hashlib.sha256(args.metadata.read_bytes()).hexdigest(),
    stack_decode_errors=[],stack_decode_error_count=0,stack_examples=[],
    total_events=0,source='tracerpt -rts on the retained ETL')


def number(value):
    return int(value,16 if value.lower().startswith('0x') else 10)


for action,elem in parse:
    if action!='end' or elem.tag!='{'+ns['e']+'}Event':continue
    result['total_events']+=1
    system=elem.find('e:System',ns)
    data={e.get('Name'):e.text.strip() if e.text else '' for e in elem.findall('e:EventData/e:Data',ns)}
    rendering=elem.find('e:RenderingInfo',ns)
    info={e.tag.split('}')[-1]:e.text for e in rendering} if rendering is not None else {}
    event_guid=elem.findtext('t:ExtendedTracingInfo/t:EventGuid',namespaces=ns)
    timestamp=system.find('e:TimeCreated',ns)
    execution=system.find('e:Execution',ns)
    event=dict(time=timestamp.attrib if timestamp is not None else {},
        execution=execution.attrib if execution is not None else {},info=info,data=data,
        opcode=system.findtext('e:Opcode',namespaces=ns),event_guid=event_guid)
    target=number(data['ProcessId']) if data.get('ProcessId') else None
    if info.get('EventName')=='EventTrace' and info.get('Opcode')=='Header':
        result['headers'].append(event)
    elif info.get('EventName')=='PageFault' and info.get('Opcode') in ('VirtualAlloc','VirtualFree') and target==pid:
        result['events'].append(event)
    elif info.get('EventName')=='Image' and target in (0,pid):
        result['images'].append(event)
    elif (event_guid or '').lower()=='{def2fe46-7bd6-4b80-bd94-f57fe20d0ce3}' and event['opcode']=='32':
        if len(result['stack_examples'])<2:result['stack_examples'].append(ET.tostring(elem,encoding='unicode'))
        payload=elem.findtext('e:ProcessingErrorData/e:EventPayload',namespaces=ns)
        try:
            if payload:
                raw=bytes.fromhex(payload)
                if len(raw)<16 or (len(raw)-16)%8:raise ValueError('Invalid x64 StackWalk payload length')
                qpc,stack_pid,thread=struct.unpack_from('<QII',raw)
                frames=[hex(value[0]) for value in struct.iter_unpack('<Q',raw[16:])]
            else:
                qpc,stack_pid,thread=(number(data[key]) for key in ('EventTimeStamp','StackProcess','StackThread'))
                indexed=sorted((int(key[5:]),number(value)) for key,value in data.items() if re.fullmatch(r'Stack\d+',key))
                if [i for i,_ in indexed]!=list(range(1,len(indexed)+1)):
                    raise ValueError('Non-contiguous decoded stack frames')
                frames=[hex(address) for _,address in indexed]
            if stack_pid==pid:
                result['stacks'].append(dict(qpc=qpc,pid=stack_pid,thread=thread,time=event['time'],
                    frames=frames,raw_payload=payload,decoded_data=data if not payload else None))
        except (KeyError,ValueError) as error:
            result['stack_decode_error_count']+=1
            if len(result['stack_decode_errors'])<8:result['stack_decode_errors'].append(str(error))
    elem.clear();root.clear()
result['metadata_image_sha256']=metadata['executable_sha256']
args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
assert result['headers'] and all(number(h['data']['PointerSize'])==8 for h in result['headers'])
assert result['events'] and result['stacks'] and not result['stack_decode_errors'],dict(
    events=len(result['events']),stacks=len(result['stacks']),errors=result['stack_decode_errors'],
    examples=result['stack_examples'])
print(json.dumps(dict(pid=pid,total_events=result['total_events'],vm_events=len(result['events']),
    stacks=len(result['stacks']),images=len(result['images']),
    sample_event=result['events'][0],sample_stack={k:v for k,v in result['stacks'][0].items() if k!='raw_payload'}),indent=2))
