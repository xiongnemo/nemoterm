/* Test-only D3D11 HRESULT injection for one owned frontend.
 * SDK ABI: QI 0, Release 2, GetAdapter 7, GetParent 6,
 * CreateSwapChain 10, Present 8, ResizeBuffers 13; OutputWindow offset 48.
 * No production fault message or renderer switch is introduced. */
if(Process.pointerSize!==8)throw new Error('Only Windows x64 is validated');
const parentWindow=new NativeFunction(Process.getModuleByName('user32.dll').getExportByName('GetParent'),'pointer',['pointer']);
const images=Process.enumerateModules().filter(m=>m.path.toLowerCase()===ownedImagePath.toLowerCase());
if(images.length!==1)throw new Error('Expected exactly one owned executable module');
const executable=images[0];
let armed='',hits=[],serial=0,attempts=[],targets=new Map(),hooks=new Map();
function method(o,s){return o.readPointer().add(s*Process.pointerSize).readPointer();}
function guid(p){return Array.from(new Uint8Array(p.readByteArray(16))).map(x=>x.toString(16).padStart(2,'0')).join('');}
function callerOwned(p){return p.compare(executable.base)>=0 && p.compare(executable.base.add(executable.size))<0;}
function hook(p,name,callbacks){
    const key=name+p;
    if(!hooks.has(key))hooks.set(key,{address:p,listener:Interceptor.attach(p,callbacks)});
}
function selected(o,kind){const item=targets.get(o.toString());return item && item.kinds.has(kind)?item:null;}
function inject(result,name){
    if(armed!==name)return;
    hits.push({fault:name,original:result.toInt32()});armed='';
    result.replace(ptr(name==='device'?'0x80004005':'0x887a0005'));
}
function remember(o,kind,owner){
    const key=o.toString();let item=targets.get(key);
    if(!item || item.owner!==owner){item={owner,kinds:new Set()};targets.set(key,item);}
    item.kinds.add(kind);
    hook(method(o,2),'release',{
        onEnter(args){this.key=args[0].toString();this.item=targets.get(this.key);},
        onLeave(result){
            if(result.toInt32()!==0 || !this.item)return;
            targets.delete(this.key);
            if(this.item.kinds.has('device'))for(const [key,item] of targets)
                if(item.owner===this.item.owner)targets.delete(key);
        }
    });
}
function swapchain(o,owner){
    remember(o,'swap',owner);
    for(const [name,slot] of [['present',8],['resize',13]])hook(method(o,slot),name,{
        onEnter(args){this.owned=!!selected(args[0],'swap');},
        onLeave(result){if(this.owned)inject(result,name);}
    });
}
function factory(o,owner){
    remember(o,'factory',owner);
    hook(method(o,10),'swapchain',{
        onEnter(args){
            const item=selected(args[0],'factory');
            this.owner=item && parentWindow(args[2].add(48).readPointer()).equals(ownedWindow)?item.owner:0;
            this.output=args[3];
        },
        onLeave(result){if(this.owner && result.toInt32()>=0 && !this.output.readPointer().isNull())swapchain(this.output.readPointer(),this.owner);}
    });
}
function adapter(o,owner){
    remember(o,'adapter',owner);
    hook(method(o,6),'parent',{
        onEnter(args){
            const item=selected(args[0],'adapter');
            this.owner=item && guid(args[1])==='ec66717bc721ae44b21ac9ae321ae369'?item.owner:0;
            this.output=args[2];
        },
        onLeave(result){if(this.owner && result.toInt32()>=0 && !this.output.readPointer().isNull())factory(this.output.readPointer(),this.owner);}
    });
}
function dxgi(o,owner){
    remember(o,'dxgi',owner);
    hook(method(o,7),'adapter',{
        onEnter(args){const item=selected(args[0],'dxgi');this.owner=item?item.owner:0;this.output=args[1];},
        onLeave(result){if(this.owner && result.toInt32()>=0 && !this.output.readPointer().isNull())adapter(this.output.readPointer(),this.owner);}
    });
}
function device(o,owner){
    remember(o,'device',owner);
    hook(method(o,0),'query',{
        onEnter(args){
            const item=selected(args[0],'device');
            this.owner=item && guid(args[1])==='fa77ec547713e6448c3288fd5f44c84c'?item.owner:0;
            this.output=args[2];
        },
        onLeave(result){if(this.owner && result.toInt32()>=0 && !this.output.readPointer().isNull())dxgi(this.output.readPointer(),this.owner);}
    });
}
const observer=Process.attachModuleObserver({
    onAdded(module){
        if(module.name.toLowerCase()!=='d3d11.dll')return;
        hook(module.getExportByName('D3D11CreateDevice'),'device',{
            onEnter(args){
                this.owned=callerOwned(this.returnAddress);this.output=args[7];
                const module=Process.findModuleByAddress(this.returnAddress);
                if(attempts.length<64)attempts.push({owned:this.owned,caller:this.returnAddress.toString(),
                    module:module?module.name:null,rva:module?this.returnAddress.sub(module.base).toString():null});
            },
            onLeave(result){
                if(!this.owned)return;
                if(result.toInt32()>=0 && !this.output.readPointer().isNull())device(this.output.readPointer(),++serial);
                inject(result,'device');
            }
        });
    },
    onRemoved(module){
        for(const [key,value] of hooks)if(value.address.compare(module.base)>=0 && value.address.compare(module.base.add(module.size))<0){
            value.listener.detach();hooks.delete(key);
        }
        if(module.name.toLowerCase()==='d3d11.dll')targets.clear();
    }
});
rpc.exports.arm=function(name){
    if(!['','device','present','resize'].includes(name))throw new Error('Unknown fault');
    armed=name;hits=[];
};
rpc.exports.status=function(){return {armed,hits,targets:targets.size,hooks:hooks.size,attempts,executable:executable.name};};
