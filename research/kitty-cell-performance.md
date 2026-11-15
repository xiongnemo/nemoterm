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

No production optimization has been made yet. The first remote baseline is
pending; local native testing remains paused by the user. Full native CI at
`eae8968` continues independently, including the new dense-cell memory fixture.
