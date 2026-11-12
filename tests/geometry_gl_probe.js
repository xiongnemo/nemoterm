/* Observation only: attach to the fixture-owned frontend, never change calls. */
let count = 0, begins = 0, paints = 0;
function report(event) { if (count++ < 180) send(event); }
function hook(module, name, callbacks) {
    try { Interceptor.attach(Process.getModuleByName(module).getExportByName(name), callbacks); }
    catch (e) { report({name, error:String(e)}); }
}
hook('opengl32.dll', 'wglMakeCurrent', {
    onEnter(args) { this.dc=args[0].toString(); this.gl_context=args[1].toString(); },
    onLeave(result) { report({name:'wglMakeCurrent', dc:this.dc,context:this.gl_context,result:result.toInt32()}); }
});
hook('opengl32.dll', 'glGetError', {
    onLeave(result) { if (result.toInt32()) report({name:'glGetError',result:result.toInt32()}); }
});
hook('opengl32.dll', 'glViewport', {
    onEnter(args) { report({name:'glViewport',box:[0,1,2,3].map(i=>args[i].toInt32())}); }
});
let reads = 0, uploads = 0, stretches = 0;
hook('opengl32.dll', 'glReadPixels', {
    onEnter(args) { this.out=args[6]; this.xywh=[0,1,2,3].map(i=>args[i].toInt32()); },
    onLeave() {
        if (reads++ < 8) report({name:'glReadPixels',box:this.xywh,
            pixels:[0,4,8,32].map(n=>this.out.add(n).readU32())});
    }
});
hook('opengl32.dll', 'glTexImage2D', {
    onEnter(args) {
        if (!args[8].isNull() && uploads++ < 8)
            report({name:'glTexImage2D',size:[args[3].toInt32(),args[4].toInt32()],
                pixels:[0,4,8].map(n=>args[8].add(n).readU32())});
    }
});
const getObjectType = new NativeFunction(Process.getModuleByName('gdi32.dll').getExportByName('GetObjectType'),'uint',['pointer']);
const getClipBox = new NativeFunction(Process.getModuleByName('gdi32.dll').getExportByName('GetClipBox'),'int',['pointer','pointer']);
const getWindowLong = new NativeFunction(Process.getModuleByName('user32.dll').getExportByName('GetWindowLongPtrW'),'pointer',['pointer','int']);
let windowPaints=0;
Interceptor.attach(getWindowLong(ownedWindow,-4), {
    onEnter(args) {
        const msg=args[1].toUInt32();
        if ([15,20,0x317,0x318].includes(msg) && windowPaints++<16)
            report({name:'WndProc',msg,wp:args[2].toString(),lp:args[3].toString(),dc_type:getObjectType(args[2])});
    }
});
hook('gdi32.dll', 'StretchDIBits', {
    onEnter(args) {
        if (stretches < 8) {
            const rect=Memory.alloc(16);
            this.clip=getClipBox(args[0],rect);
            this.dc_type=getObjectType(args[0]);
            this.box=[0,4,8,12].map(n=>rect.add(n).readS32());
        }
    },
    onLeave(result) { if (stretches++ < 8) report({name:'StretchDIBits',result:result.toInt32(),
        error:this.lastError,dc_type:this.dc_type,clip:this.clip,box:this.box}); }
});
hook('user32.dll', 'BeginPaint', {
    onLeave(result) { if (paints++ < 8) report({name:'BeginPaint',dc:result.toString(),dc_type:getObjectType(result)}); }
});
hook('gdi32.dll', 'SwapBuffers', {
    onLeave(result) { report({name:'SwapBuffers',result:result.toInt32()}); }
});
hook('opengl32.dll', 'glBegin', {
    onEnter(args) { if (begins++ < 4) report({name:'glBegin',mode:args[0].toInt32()}); }
});
report({name:'attached',pid:Process.id});
