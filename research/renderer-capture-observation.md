# Renderer capture failure and API comparison

The accepted-candidate CI image for `3187ec51acb703adebf006fd637c1ad80fba8b43`
has SHA-256 `8e52b517787fb508937611b15eb48855ab0e73521978f579d853cf48d9748585`.
Its first local renderer parity run failed while the old Frida capture RPC read
the resized OpenGL frame: `access violation accessing 0x0`, reported from
`/script1.js:38`. The eight processes in the controller's private job all exited
naturally. This is an observed capture-path error; no native crash dump or stack
establishes its underlying cause. The failing log and partial results remain in
the [validation manifest](renderer-capture-validation.json).

One finite replay with the original fixture passed all 20 scenes on actual GDI,
OpenGL and DirectX. The updated fixture then passed the same 60 comparisons and
semantic pixel assertions against the same executable. It replaces only the
GPU frame capture with `OwnedAutomationCapture`, adds `--automation` to owned
launches, and records the observation method. GDI still uses independent
PrintWindow capture. The owned-process focus probe still uses Frida to hold
active and inactive cursor states, and memory samples remain marked instrumented.
This is not a claim of a completely injection-free renderer test.

The change removes the failing process-local capture RPC from this test. It
does not establish why that RPC failed, nor does a passing replay resolve the
separate hosted CI exit timeouts. Pixel tolerances, all 20 scenes, focus behavior
and actual-renderer requirements are unchanged. The manifest retains 179
compressed records (2,230,083 bytes), including the failure, original and new
fixtures, focus/capture probes, screenshots, results and natural job cleanup.
