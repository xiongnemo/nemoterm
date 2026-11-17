# Pinned ncurses key data

`nemo_tcap_database.inc` is the unchanged generated artifact from hosted run
44072637041, SHA-256
`809c721a29b66764ee109420be1ff18cde3e3248f3dde8f78e8474700d9eaadc`.
The adjacent manifest identifies the pinned ncurses/XTerm source revisions,
the library, rejected terminal aliases and table sizes. `COPYING.ncurses`
contains the upstream license. The original terminfo source and complete
observations are retained in `research/terminfo-database-evidence.zip`.

Regenerate and verify only through the hosted `protocol-reference.yml` workflow
with `family=terminfo-database`. `scripts/export-terminfo-database.py` compiles
all upstream aliases and reads XTerm's key capability names using upstream
libtinfo. Do not edit generated key strings by hand.
