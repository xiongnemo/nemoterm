/* Explicitly scoped virtual pointer for the fixture-owned host. Native cursor
 * messages can follow repaint/resize even when the physical pointer is still.
 * During the hover phase, accept the controller's cross-thread SendMessage
 * moves/leaves and ignore queued physical-pointer notifications. Timers and
 * product preview rendering remain real. No global cursor or input is changed. */
const hoverUser=Process.getModuleByName('user32.dll');
const trackAddress=hoverUser.getExportByName('TrackMouseEvent');
const originalTrack=new NativeFunction(trackAddress,'int',['pointer']);
Interceptor.replace(trackAddress,new NativeCallback(function(event) {
    if (event.add(8).readPointer().equals(ownedHost)) return 1;
    return originalTrack(event);
},'int',['pointer']));
const inSend=new NativeFunction(hoverUser.getExportByName('InSendMessageEx'),'uint',['pointer']);
const getProc=new NativeFunction(hoverUser.getExportByName('GetWindowLongPtrW'),'pointer',['pointer','int']);
let virtualPointer=false;
let observations={moves:0,leaves:0,ignored:0,timers:0,events:[]};
Interceptor.attach(getProc(ownedHost,-4),{
    onEnter(args) {
        if (!virtualPointer || !args[0].equals(ownedHost)) return;
        const msg=args[1].toUInt32();
        if (msg===0x113 && args[2].toUInt32()===1) {observations.timers++;return;}
        if (msg!==0x200 && msg!==0x2a3) return;
        const flags=inSend(ptr(0));
        const ignored=(flags&7)===0;
        observations.events.push({msg,flags,lp:args[3].toInt32(),ignored});
        if(observations.events.length>128)observations.events.shift();
        if (ignored) {observations.ignored++;args[1]=ptr(0);}
        else if(msg===0x200) observations.moves++;
        else observations.leaves++;
    }
});
rpc.exports={
    begin() {virtualPointer=true;},
    stats() {return observations;}
};
