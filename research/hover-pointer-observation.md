# Controlled hover pointer and remaining resource failures

The `3187ec5` CI image (`8e52b517787fb508937611b15eb48855ab0e73521978f579d853cf48d9748585`)
failed a local tab-preview check. An owned-window message trace showed the
fixture's hover at `(96,14)` followed by repeated moves at `(137,452)`, with no
preview timer. The latter coordinates replace the tab hover before its 400 ms
timer can fire. Simulating TrackMouseEvent alone does not stop other mouse
messages delivered to the fixture window.

`tabs_hover_probe.js` now scopes a virtual pointer to the explicit preview
phase. For this one owned host, it accepts cross-thread SendMessage moves and
leaves, and changes queued mouse-move/leave notifications to WM_NULL. It uses
InSendMessageEx to distinguish these delivery paths, retains bounded event
records and counters, and leaves real timers, thumbnail generation and window
visibility checks unchanged. The system cursor and unrelated windows are not
touched. This remains injected test instrumentation, installed after the
uninstrumented memory sampling phase; it changes no product behavior.

A controlled canary sends the desired synchronous hover, then posts an
out-of-bounds mouse move to the same owned host. With filtering disabled, the
trace records flags 1 then 0, two accepted moves, no timer and the expected
preview timeout. With filtering enabled, GDI/top, DirectX/left and OpenGL/bottom
each pass all nine tab checks: the queued move is ignored, the real timer fires,
the background preview updates, and an explicit leave hides it. Jobs in these
three passing runs drain naturally. This reproduces the pointer-model conflict
without moving the user's physical cursor.

The first OpenGL/bottom run and the DirectX/right run failed earlier in the
independent closed-tab resource-return gate, before this hover probe was
installed. The subsequent OpenGL run passed; the DirectX/right run did not reach
the preview check. Those failures remain retained and unresolved; resource
thresholds and timeouts were not changed. The inline-image DirectX memory
overrun is also separate and remains unresolved. The controlled canary's
expected failure requires private-job cleanup and is never counted as product
acceptance. Hosted CI still needs to validate the fixture changes.

The [manifest](hover-pointer-validation.json) retains the original message
trace, controlled variants, exact test sources, all successful and failed
results, resource samples, screenshots and cleanup records.
