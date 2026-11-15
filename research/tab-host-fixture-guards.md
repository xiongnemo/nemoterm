# Verify the actual host before recording tab coverage

The CLI precedence defect showed that a requested `--tabs` flag is not proof
that a fixture exercised a tab host. Input and selection already check the
actual root window. Geometry, application resizing and the real Codex fixture
now also record `requested_tab_host`, the observed `tab_host` and the root
window class. They reject the wrong host before input, clipboard or geometry
assertions. Each geometry/resize profile records its own observed host class.

The original `12ee33b` single image is a negative control: both hosted geometry
and resize commands stop at the new guard with class `Nemoterm`, before any
geometry phase. The corrected portable frontend retained in
[host-restore-size.md](host-restore-size.md) passes both commands in hosted and
standalone mode: four invocations, 130 unchanged geometry/resize stages and
natural process cleanup. The failed negative controls retain their original
failure/cleanup evidence; they are intentional guard rejections, not passing
product tests.

`tab-host-fixture-guards.tar.gz` retains the original reports, logs, captures,
controller and three changed fixture sources. The adjacent validation manifest
contains their hashes and both executable identities. Fixture dependencies are
from source `d914972`; these are additional local fixture assertions, not part
of that source's already-running CI. No product source is changed here.

The Codex fixture has the same guard before its first clipboard operation.
Its new real-client replay remains pending while the local Windows desktop is
locked. These bounded passes do not certify physical IME, clipboard access,
multi-monitor DPI or the complete v0 requirements.
