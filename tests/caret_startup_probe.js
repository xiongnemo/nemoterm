// Installed before the owned frontend enters WinMain. Observe, do not replace,
// its caret API calls, including focus delivered by initial SetWindowPos.
const user=Process.getModuleByName('user32.dll');
const name=new NativeFunction(user.getExportByName('GetClassNameW'),'int',['pointer','pointer','int']);
const events=[];
Interceptor.attach(user.getExportByName('CreateCaret'),{
    onEnter(args) {
        const text=Memory.alloc(256);name(args[0],text,128);
        if(text.readUtf16String()!=='Nemoterm')return;
        this.event={hwnd:args[0].toString(),bitmap:args[1].toString(),
            width:args[2].toInt32(),height:args[3].toInt32()};
    },
    onLeave(result) {
        if(this.event){this.event.result=!!result.toInt32();events.push(this.event);}
    }
});
rpc.exports={events(){return events;}};
