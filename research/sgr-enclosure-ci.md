# SGR enclosure CI artifact checkpoint

At source `7a97307d24e58f38fdcd8a67a249c596280a7815`, both full workflows pass:
[core and sanitizers](https://github.com/xiongnemo/nemoterm/actions/runs/43557702273)
and [single executable](https://github.com/xiongnemo/nemoterm/actions/runs/43557702284).
The single workflow reports 102 checks. This supersedes the earlier missing
generated-fixture CI failure as a CI result; its original records remain retained.

The downloaded [artifact](https://github.com/xiongnemo/nemoterm/actions/runs/43557702284/artifacts/14099283980)
contains a 4,451,840-byte executable with SHA-256
`4b7df978d3a4be3782ac28940619c222fd67f155e202f69692e5a6635fbd3288`.
The following local results use these exact bytes, fresh private jobs and actual
SarasaTermSC Nerd Font Light rendering. The image has not replaced `dist`.

* All 18 renderer scenes pass in actual GDI, OpenGL and DirectX. These independent
  capture checks are instrumented and are not memory acceptance.
* All 239 ConPTY reply cases pass: 193 unchanged XTerm references and 46 explicit
  extension cases. The renderer and wire jobs exit naturally with no survivors.
* The GDI 160x48 workload passes all nine groups. Its 469 samples peak at
  16,740,352 bytes private working set, 43,560,960 total working set and
  19,275,776 private commit. All 56 inner / 58 outer processes exit naturally.
* DirectX fails its second post-close resource assertion: handles 489 -> 540,
  GDI objects 38 -> 38, USER objects 40 -> 54. Both tracked stream workers have
  signaled. Its 57 early samples stop before the full workload and do not
  establish DirectX memory acceptance. The inner private job terminates five
  remaining owned processes; the outer job subsequently confirms no survivors.

The resource limits remain unchanged. A green CI run does not supersede this
local failure. Delayed input-method initialization and temporary GUI resources
are still being investigated separately from SGR rendering.

The [manifest](sgr-enclosure-ci-validation.json) retains 91 compressed records
(996,112 bytes), including exact CI identities, local pixels, replies, resource
samples, failed assertions and cleanup results. Every decompressed length and
SHA-256 was verified. These are CI/local observations, not REA-server Evidence.
See [the implementation checkpoint](sgr-enclosures.md) for semantics and limits.
