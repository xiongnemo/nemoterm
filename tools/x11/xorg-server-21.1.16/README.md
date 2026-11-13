# Pinned X11 named-colour data

`oscolor.c` is the unmodified `os/oscolor.c` member of the official
[Xorg server 21.1.16 source archive](https://xorg.freedesktop.org/archive/individual/xserver/xorg-server-21.1.16.tar.xz).
`manifest.json` records the observed SHA-256 of that HTTPS download and the
retained files. This is a content pin, not a claim of signature verification.
`LICENSE.txt` preserves the notices at the top of that source file.

Only its fixed colour-name/RGB table is used. No X server code is compiled or
executed, and no X11 library, server or runtime data file is shipped. The version
matches the upstream version of the installed Xvfb reference environment; this
does not assert that any particular XTerm/Xlib installation uses identical
client-side colour resources.

`python scripts/generate-x11-colours.py` verifies the input hashes, decodes and
cross-checks the upstream name offsets, then emits a compact read-only product
table and source-derived test vectors. `--check` verifies regeneration without
writing. The generated files are committed, so an ordinary product build does
not need Python. Notices are embedded in the single EXE's `--licenses` resource;
the multi-file comparison package copies them alongside its other licences.
