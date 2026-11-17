# Execution policy

The user requires all automated builds and tests to run on GitHub-hosted
Actions runners. Do not run product binaries, compilers, test suites, runtime
probes or reference captures on the development computer, including through
WSL or a local container. Do not use its desktop, focus, clipboard, sound or
display configuration for acceptance.

Local source editing, Git operations, workflow dispatch/status queries, artifact
downloads and read-only analysis of downloaded records/images/binaries are
allowed. A successful older executable does not validate a newer executable.

Use `ci.yml` with `scope=full` for aggregate regression. For exact-image replay
and upstream reference collectors, use the entries in
`docs/INTERACTION_ACCEPTANCE.md`. Retain failures, product/fixture identities
and original evidence; do not waive gates or overwrite historical failures to
obtain a green run. User instructions in the active conversation take priority.
