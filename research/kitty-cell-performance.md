# Dense image-cell placement measurements

The Unicode memory fixture can create 7,268 independent image-cell runs at
160x48. Source inspection finds three linear searches repeated per run:
prototype selection during admission, sorted list insertion, and prototype
identity lookup while obtaining a drawing view. The existing boundary test
admits 8,192 cells, but does not establish repaint performance at that density.

`test_kitty_placements --benchmark-cells` measures the unchanged production
owner at 256, 512, 1,024, 2,048, 4,096, 7,268 and 8,192 cells, with one and
sixteen virtual templates. Each sample creates independent cells, reads every
view four times, then removes the cells. Three repetitions retain raw C
`clock()` ticks and `CLOCKS_PER_SEC`, placement bytes, baseline ownership and
the shared cache/placement peak. Every cell must be admitted and yield its
expected image, order and rectangle; cleanup restores template-only ownership.
The ordinary correctness suite remains separate.

This is an opt-in component measurement, run in remote GCC, Clang and MSVC
jobs without a terminal window. It includes assertion/iteration costs and
allocator effects. Clock semantics and resolution differ across runtimes;
raw values are comparable only within matched compiler/runtime environments.
It does not measure parsing, raster painting, GPU presentation, process working
set or interactive latency, and has no arbitrary timing pass threshold.

The first [remote baseline](https://github.com/xiongnemo/nemoterm/actions/runs/43684451421)
passes all three compilers at `a7e40bd`. With 7,268 cells and one template, median
creation/view-pass times are 104.403/93.878 ms for GCC, 98.770/88.172 ms for Clang
and 183/231.25 ms for MSVC. At 8,192 cells, the corresponding values are
131.562/118.992, 124.386/112.311 and 235/310.25 ms. These are distinct hosted
machines/runtimes and are not a compiler ranking. Sixteen-template samples and
all three raw repetitions are retained in the component artifacts.

The proposed optimization keeps a sequence-sorted prototype index and per-image
cell insertion hints in the placement owner. Unlinking or replacing a placement
invalidates the hints before a borrowed pointer can expire. Template replacement
preserves identity; removing or converting a template updates the index.
Character and placement object sizes are unchanged. The bounded tables are
allocated only on the first virtual template and freed when the last template
is removed or converted to an ordinary placement. They remain charged to the
shared 4 MiB image budget (roughly 5 KiB while present on x64); no run count or
image cap is raised. Admission covers the whole index and new placement before
either is committed, including in-place conversions.

The component workflow compiles the original placement source from full commit
`a7e40bdc698dfa268b2bebe8c426d82e7a2d9130` beside the candidate, with identical
current tests and compiler flags, then measures both on the same runner. The
baseline placement source SHA256 is
`1e3e8a381108afbf1be5e539dfb5ffd845b36d03e790f13975606fcd600457b0`.
Additional correctness cases fill all 512 templates across 128 images, alternate
image insertion order, replace/convert templates and remove/recreate cell runs.
The lazy-index candidate passes
[all three component jobs](https://github.com/xiongnemo/nemoterm/actions/runs/43686139850)
at `5f0c70f`, including GCC/Clang ASan/UBSan, 19,749 placement assertions, the
under-8-KiB empty-owner check, 238 relative states, 728 Unicode states and 32
exact core copies. No runtime test has been run on the paused local desktop.

The first candidate `e05a60f` failed its complete component workflow: MSVC rejected
a shadowed local variable, and GCC/Clang reported that its fixed owner tables
violated the existing under-8-KiB empty terminal graphics-owner check. All 728
Unicode states, 238 relative states and 32 core copies still passed, as did
19,708 placement checks. The later on-demand allocation corrects this idle
overhead instead of relaxing that assertion. The failed run and its paired
timings remain retained separately; partial passes do not make that run green.

For 7,268 cells and one template, matched runner medians are:

| Compiler/runtime | Create before / after (ms) | One view pass before / after (ms) |
| --- | ---: | ---: |
| GCC / Linux | 83.464 / 0.440 | 75.461 / 0.094 |
| Clang / Linux | 167.996 / 0.744 | 202.372 / 0.117 |
| MSVC / Windows | 128 / 1 | 231.75 / 0.25 |

MSVC clock resolution is 1 ms; four view passes are timed together, so a zero
sample in another case means below clock resolution, not zero work. The active
placement owner adds 5,136 bytes on these x64 builds, including the 8-byte owner
pointer that remains when no virtual templates exist. Per-cell and per-placement
sizes remain unchanged. `kitty-cell-performance-validation.json` preserves all
42 samples per compiler/arm and verifies each paired baseline source hash.
The archive also retains the first candidate's failures. A later
[native source diagnostic](unicode-dense-memory.md) completes 24 dense-image
resizes per renderer on the remote grids without reaching its 30-second snapshot
threshold. It is explicitly separate from memory acceptance and post-memory
pixel verification. The later ordinary CI at `f01927a` passes the full dense-cell
gate on remote Consolas grids, including all post-memory cell-centre checks.
A pre-index source reproduction captures the busy thread inside linear prototype
lookup at both 30 and 60 seconds. The [native record](unicode-dense-memory.md)
distinguishes those rebuilt images from the missing original failure. Single-file
and local 160x48 Sarasa exact-product acceptance remain pending.
