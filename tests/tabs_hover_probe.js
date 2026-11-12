/* Only the fixture-owned host's leave tracking is simulated. The controller
 * sends WM_MOUSEMOVE / WM_MOUSELEAVE explicitly; no system cursor is moved. */
const trackAddress=Process.getModuleByName('user32.dll').getExportByName('TrackMouseEvent');
const originalTrack=new NativeFunction(trackAddress,'int',['pointer']);
Interceptor.replace(trackAddress,new NativeCallback(function(event) {
    if (event.add(8).readPointer().equals(ownedHost)) return 1;
    return originalTrack(event);
},'int',['pointer']));
