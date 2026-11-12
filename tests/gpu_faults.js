/* Test-only HRESULT injection in one fixture process. Vtable slots derive
 * from the public d2d1.h ABI: factory 14, compatible 12, EndDraw 49, Resize 58.
 * No production control message or fault switch is added to the terminal. */
const parentWindow = new NativeFunction(Process.getModuleByName('user32.dll').getExportByName('GetParent'),'pointer',['pointer']);
let armed='', hits=[], targets=new Map(), hooks=new Map();
function hook(address, name, callbacks) {
    const key=name+address;
    if (!hooks.has(key)) hooks.set(key,Interceptor.attach(address,callbacks));
}
function method(object,slot) {return object.readPointer().add(slot*Process.pointerSize).readPointer();}
function inject(result,name) {
    if (armed!==name) return;
    hits.push({fault:name,original:result.toInt32()});armed='';
    result.replace(ptr(name==='factory'?'0x80004005':'0x8899000c'));
}
function target(object,kind) {
    targets.set(object.toString(),kind);
    hook(method(object,2),'release',{
        onEnter(args){this.object=args[0].toString();},
        onLeave(result){if (result.toInt32()===0) targets.delete(this.object);}
    });
    hook(method(object,49),'enddraw',{
        onEnter(args){this.owned=targets.has(args[0].toString());},
        onLeave(result){if(this.owned)inject(result,'draw');}
    });
    if(kind==='window') {
        hook(method(object,58),'resize',{
            onEnter(args){this.owned=targets.get(args[0].toString())==='window';},
            onLeave(result){if(this.owned)inject(result,'resize');}
        });
        hook(method(object,12),'compatible',{
            onEnter(args){this.owned=targets.has(args[0].toString());this.output=args[5];},
            onLeave(result){if(this.owned && result.toInt32()>=0 && !this.output.readPointer().isNull())target(this.output.readPointer(),'frame');}
        });
    }
}
const observer=Process.attachModuleObserver({
    onAdded(module) {
        if(module.name.toLowerCase()!=='d2d1.dll')return;
        hook(module.getExportByName('D2D1CreateFactory'),'factory',{
            onEnter(args){this.output=args[3];},
            onLeave(result){
                if(result.toInt32()>=0 && !this.output.readPointer().isNull()) {
                    hook(method(this.output.readPointer(),14),'hwnd',{
                        onEnter(args){this.owned=parentWindow(args[2].readPointer()).equals(ownedWindow);this.output=args[3];},
                        onLeave(result){if(this.owned && result.toInt32()>=0 && !this.output.readPointer().isNull())target(this.output.readPointer(),'window');}
                    });
                }
                inject(result,'factory');
            }
        });
    },
    onRemoved(module) {
        if(module.name.toLowerCase()!=='d2d1.dll')return;
        for(const value of hooks.values())value.detach();
        hooks.clear();targets.clear();
    }
});
rpc.exports.arm=function(name) {
    if(!['','factory','draw','resize'].includes(name))throw new Error('Unknown fault');
    armed=name;hits=[];
};
rpc.exports.status=function(){return {armed,hits,targets:targets.size};};
