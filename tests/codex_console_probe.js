// Optional diagnostic trace, attached only to the newly launched Codex PID.
// The mutation switch must never be enabled during product acceptance.
const K = Process.getModuleByName('kernelbase.dll');
const suppress = false;
let events = 0;
for (const name of ['ReadConsoleInputW','PeekConsoleInputW']) {
    Interceptor.attach(K.getExportByName(name), {
        onEnter(a) { this.buffer=a[1]; this.count=a[3]; this.capacity=a[2].toUInt32(); },
        onLeave(result) {
            if (result.toInt32()===0 || events>512) return;
            const count=Math.min(this.capacity,this.count.readU32(),128), values=[];
            for(let i=0;i<count;i++) {
                const p=this.buffer.add(i*20), type=p.readU16();
                if(type===1) values.push({type,down:p.add(4).readS32(),repeat:p.add(8).readU16(),
                    vk:p.add(10).readU16(),scan:p.add(12).readU16(),character:p.add(14).readU16(),control:p.add(16).readU32()});
                else values.push({type});
                if(suppress && name==='ReadConsoleInputW' && type===1 && !p.add(4).readS32() &&
                   p.add(14).readU16()>=0xd800 && p.add(14).readU16()<=0xdfff) p.add(14).writeU16(0);
            }
            if(count) { events+=count; send({name,values}); }
        }
    });
}
send({ready:true});
