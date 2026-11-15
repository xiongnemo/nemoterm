# Query errors must not discard a pending Kitty upload

The accepted `6e05bd1` image loses an unfinished image transfer when certain
interleaved query headers are malformed. The pending input buffer is freed before
the owner can decide to discard the query. The visible result is a missing image
when the application's final chunk arrives. This is a protocol/state bug, not
the unrelated historical native access violation.

The [feature-query specification](https://sw.kovidgoyal.net/kitty/graphics-protocol/#querying-support-for-protocol-features)
requires queries to leave in-progress transfers unchanged. A new pinned upstream
capture tests six valid field orders, fourteen unusual/error fields in three
positions, duplicate selectors/actions, malformed ordinary headers and a data-error
control. [Reference run 43658981873](https://github.com/xiongnemo/nemoterm/actions/runs/43658981873)
passes **54 cases / 216 states** under REA 6.8.0, without capture truncation and
with verified process-group cleanup. Upstream remains
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`; the original 84-case reference is unchanged.

All 53 header/query cases retain the pending upload and complete its green image.
The data-error control ends that upload and leaves the seed visible. The record
retains each original reply, cursor, image count and layer geometry. Its 109 empty
upstream image slots are kept separately from complete images. The one data-error
reply compares the same image-ID/error envelope: the strict local base64 parser
and upstream decoder report different error codes/descriptions. Other replies
remain exact byte comparisons, including identity errors.

Before the fix, the real terminal-core replay mismatches **35 cases**. The exact
accepted single EXE also fails a native GDI replay at stage 40: after a malformed
query, the last image chunk returns only the input barrier and no image-completion
reply. Its owned processes still exit naturally. Both failures are retained.

The fix distinguishes rejected headers from image-data failures. Header syntax
is checked before any payload is appended; a rejected header is silently dropped
without freeing the earlier upload. Feature queries are dispatched before ordinary
upload-only checks on `m`, `q` and simultaneous IDs, so the owner can ignore the
more flag, honor quiet mode and report the identity error without altering the
pending bytes. A complete header may end with a comma, matching the reference.
Payload errors, resource limits and explicit cancellation retain their existing
paths. No rollback copy or new heap allocation is introduced.

The real core now passes all 216 new states plus the existing 101 image, 36
compression and 176 feature-query states. Transport checks pass **2,115,791
assertions**, including 1,000 rejected headers with constant input memory and a
successfully completed earlier upload.

The development frontend passes **648 native API stages** on actual GDI/OpenGL/
DirectX and **216 independent presented-GDI stages**, with exact replies/error
envelope, retained image pixels and natural cleanup. Its SHA256 is
`90e9e434ee88eaa481a7fc107a93fd5f6215f2a9ac89367ce5b783c4d6663b51`.
This local build uses separate identified ConPTY DLL/host files. The validation
index retains source/fixture hashes, baseline failures, corrected expectations,
all screenshots and raw replies. It explicitly corrects the baseline controller's
source-field ambiguity; the baseline executable and source identities are verified
separately. This is not yet new single-image or memory acceptance.

Component/full CI now checks the generated reference, and ordinary/single-image
native suites include the new replay. The accepted local executable remains
`6e05bd1` until the replacement product passes its full pipeline and local checks.
The complete graphics/protocol, real-application, physical-input and resource
requirements remain open.
