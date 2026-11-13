// Observe the fixture-owned terminal's real asynchronous clipboard delivery.
// Do not read, replace or synthesize clipboard data or input events.
let clipboardDeliveries = 0;
for (const suffix of ['A', 'W']) {
    Interceptor.attach(U.getExportByName('SendMessage' + suffix), {
        onEnter(args) {
            this.clipboardDelivery = args[0].equals(ownedClipboardWindow) &&
                args[1].toUInt32() === 0x8004; // WM_GOT_CLIPDATA
        },
        onLeave() {
            if (this.clipboardDelivery) clipboardDeliveries++;
        }
    });
}
rpc.exports.clipboardDeliveries = () => clipboardDeliveries;
