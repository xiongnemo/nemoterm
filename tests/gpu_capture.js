/* Capture one owned terminal's retained GPU frame using process-local GDI
 * objects. A foreign-process memory HDC is not a valid WM_PRINTCLIENT target. */
const user32 = Process.getModuleByName('user32.dll');
const gdi32 = Process.getModuleByName('gdi32.dll');
const call = (m,n,r,a) => new NativeFunction(m.getExportByName(n),r,a);
const clientRect = call(user32,'GetClientRect','int',['pointer','pointer']);
const windowDC = call(user32,'GetDC','pointer',['pointer']);
const releaseDC = call(user32,'ReleaseDC','int',['pointer','pointer']);
const memoryDC = call(gdi32,'CreateCompatibleDC','pointer',['pointer']);
const makeDIB = call(gdi32,'CreateDIBSection','pointer',['pointer','pointer','uint','pointer','pointer','uint']);
const selectGDI = call(gdi32,'SelectObject','pointer',['pointer','pointer']);
const deleteGDI = call(gdi32,'DeleteObject','int',['pointer']);
const deleteDC = call(gdi32,'DeleteDC','int',['pointer']);
const flushGDI = call(gdi32,'GdiFlush','int',[]);
const printClient = call(user32,'SendMessageTimeoutW','pointer',
    ['pointer','uint','pointer','pointer','uint','uint','pointer']);
rpc.exports.capture = function() {
    const rect=Memory.alloc(16);
    if (!clientRect(ownedWindow,rect)) throw new Error('GetClientRect failed');
    const width=rect.add(8).readS32(), height=rect.add(12).readS32();
    if (width<=0 || height<=0 || width*height>4194304) throw new Error('Capture exceeds pixel bound');
    const size=width*height*4, info=Memory.alloc(40), bits=Memory.alloc(Process.pointerSize);
    info.writeByteArray(new Uint8Array(40));
    info.writeU32(40); info.add(4).writeS32(width); info.add(8).writeS32(-height);
    info.add(12).writeU16(1); info.add(14).writeU16(32); info.add(20).writeU32(size);
    let dc=ptr(0), mem=ptr(0), bitmap=ptr(0), old=ptr(0);
    try {
        dc=windowDC(ownedWindow); mem=memoryDC(dc);
        bitmap=makeDIB(dc,info,0,bits,ptr(0),0);
        if (dc.isNull() || mem.isNull() || bitmap.isNull()) throw new Error('Capture GDI allocation failed');
        old=selectGDI(mem,bitmap);
        const result=Memory.alloc(Process.pointerSize);
        if (printClient(ownedWindow,0x318,mem,ptr(4),2,5000,result).isNull())
            throw new Error('WM_PRINTCLIENT failed');
        flushGDI();
        const output=Memory.alloc(size+8);
        output.writeU32(width); output.add(4).writeU32(height);
        Memory.copy(output.add(8),bits.readPointer(),size);
        return output.readByteArray(size+8);
    } finally {
        if (!old.isNull()) selectGDI(mem,old);
        if (!bitmap.isNull()) deleteGDI(bitmap);
        if (!mem.isNull()) deleteDC(mem);
        if (!dc.isNull()) releaseDC(ownedWindow,dc);
    }
};
