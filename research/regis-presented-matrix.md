# ReGIS: whole and bytewise console writes, GDI and DirectX

Every window below uses the same standalone Windows executable: `2c0152c`, SHA-256 `79e504be64bfc37c2fdfaa79ae179b9a5e9da4ca08ebae29cc8782e3a28ec663`. `font-zoom-replay.yml`, `suite=regis-presented-matrix`, replays the [original XTerm input and captures](regis-first-expose.md) on GitHub-hosted Windows. Each endpoint gets a new 40×12 window, 6×13 pixel cells, and a 160×120 comparison region. The child records the calls to Win32 `WriteFile`, their byte count and the digest of what it wrote. These counts describe how the child wrote the sequence, not how ConPTY delivered it internally.

[First run, 44508304087](https://github.com/xiongnemo/nemoterm/actions/runs/44508304087) · [four original artifact ZIPs and GitHub digests](regis-presented-matrix-2c0152c.zip).

- GDI: 10/10 windows in each write mode completed acquisition, passed the red/green colour swap, and exited naturally. All 65 paired steps had identical final RGB crops, outgoing bytes, and replies between write modes. This includes intermediate frames, explicit repaint, and colour controls. The three control endpoints passed. Seven endpoints still differ from the literal XTerm reference; [the previous before/after comparison](regis-presented-pairs.md) explains the distinction between scrolling or recolouring and erasing.
- DirectX: all 20 windows reported renderer 2, but failed the parent/child size assertion **before the first screenshot**. This provides no pixel result. Commit `271bae0` adds a bounded wait for equal initial client rectangles and records size/origin changes. The size, ownership, visibility, colour and literal historical checks remain in force. No repaint is requested to make the initial wait succeed.

A separate [retained component dataset](regis-views-2c0152c.zip) from [full run 44503310589](https://github.com/xiongnemo/nemoterm/actions/runs/44503310589) contains the original whole/bytewise view reports from MSVC, GCC and Clang. Across all six reports, the 132 frame hashes and replies agree at every corresponding step in the 61 scenes; all 132 replies match the reference and five frames differ from it. These are component comparisons, not native window captures.

[Aligned replay, 44509024131](https://github.com/xiongnemo/nemoterm/actions/runs/44509024131) · [four original artifact ZIPs](regis-presented-matrix-aligned-2c0152c.zip) · [offline comparison](regis-presented-matrix-aligned-2c0152c.json). All 40 Windows processes completed and passed the two-colour calibration. All 20 DirectX child windows reached the parent's size and origin in 15–31 ms. The fixture used the actual renderer in each case; it did not request an application image or read the desktop DC.

| Final stable crop vs pinned XTerm | Before the explicit repaint (different pixels) | After (different pixels) |
| --- | ---: | ---: |
| Scroll up, step 2 | 101 | 0 |
| Scroll down, steps 1 and 2 | 303 each | 0 |
| Newline scroll, step 2 | 202 | 0 |
| Shared palette change, step 1 | 600 | 0 |
| Erase line, endpoints 1 and 2 | 0 each | 101 each |

The independently decoded crops, receipts and replies were the same for **all 65 corresponding phases in all four tracks**. This is equality between the four Windows observations, including the text and colour controls; it does not claim equality to the X11 font. Each track passed three control endpoints and failed the literal XTerm comparison at the same seven endpoints. The four jobs correctly remain red. The observation is limited to these prefixes, font, geometry and runner; it is not a general claim about other GPU drivers or inputs.

To inspect either retained archive without launching a product, use `python tools/read_regis_presented_matrix.py research/regis-presented-matrix-aligned-2c0152c.zip` (Pillow required). It checks the downloaded ZIP and screenshot hashes and the child's write receipts before comparing final RGB, output bytes and replies. Initial acquisition errors are represented explicitly.
