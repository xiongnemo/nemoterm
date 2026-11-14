"""Capture pinned kitty's native screen/graphics model on a remote Linux runner.

Run through kitty +runpy, not with Nemoterm or a Python imitation of its layout.
The screen has no OS window, so these are layout/lifetime observations, not GPU
pixels. Inputs, raw layers, cursor positions and compiled module identity remain
in the output. No production kitty files are patched.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import unittest

UPSTREAM = "8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f"
COLS, ROWS, CW, CH = 12, 8, 10, 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import kitty.fast_data_types as native
    from kitty_tests.base import BaseTest, parse_bytes
    from kitty_tests.graphics import TestGraphics
    from kitty_tests.main import env_for_python_tests

    output = Path(os.environ["NEMOTERM_KITTY_REFERENCE_OUTPUT"]).resolve()
    source = Path(os.environ["NEMOTERM_KITTY_REFERENCE_SOURCE"]).resolve()
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    assert commit == UPSTREAM, commit
    record = {
        "status": "running", "upstream_commit": commit,
        "scope": "Compiled upstream parser, image manager and screen; no OS window or GPU pixels",
        "fixture_sha256": sha(__file__), "platform": platform.platform(),
        "python": platform.python_version(),
        "source_sha256": {p: sha(source / p) for p in (
            "kitty/graphics.c", "kitty_tests/graphics.py", "docs/graphics-protocol.rst")},
        "compiled_sha256": {p: sha(source / p) for p in (
            "kitty/launcher/kitty", str(Path(native.__file__).relative_to(source)))},
        "geometry": {"columns": COLS, "rows": ROWS, "cell_width": CW, "cell_height": CH},
        "cases": [],
    }

    def save():
        output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    def capture(name, steps, start=(0, 0), layer_scrollback=None):
        helper = BaseTest()
        s = helper.create_screen(COLS, ROWS, scrollback=20, cell_width=CW, cell_height=CH)
        s.cursor.x, s.cursor.y = start
        case = {"name": name, "start": list(start), "steps": []}
        record["cases"].append(case)
        try:
            for label, data in steps:
                s.callbacks.clear()
                parse_bytes(s, data)
                observed_scroll = s.scrolled_by if layer_scrollback is None else layer_scrollback
                layers = s.grman.update_layers(
                    observed_scroll, -1, 1, 2 / s.columns, 2 / s.lines,
                    s.columns, s.lines, CW, CH)
                # Retain raw normalized coordinates as well as a reversible
                # conversion to cell pixels; no expected layout is substituted.
                boxes = []
                for layer in layers:
                    r = layer["dest_rect"]
                    boxes.append({
                        "left": round((r["left"] + 1) * s.columns * CW / 2, 6),
                        "top": round((1 - r["top"]) * s.lines * CH / 2, 6),
                        "right": round((r["right"] + 1) * s.columns * CW / 2, 6),
                        "bottom": round((1 - r["bottom"]) * s.lines * CH / 2, 6),
                    })
                case["steps"].append({
                    "label": label, "input_base64": base64.b64encode(data).decode("ascii"),
                    "reply_base64": base64.b64encode(s.callbacks.wtcbuf).decode("ascii"),
                    "cursor": [s.cursor.x, s.cursor.y], "image_count": s.grman.image_count,
                    "scrolled_by": s.scrolled_by, "layer_scrollback": observed_scroll,
                    "layers": layers, "pixel_boxes": boxes,
                })
                save()
            print(f"Captured {name}: {len(steps)} states", flush=True)
        finally:
            s.reset()
            helper.tearDown()

    def command(header, payload=b""):
        return b"\x1b_G" + header.encode("ascii") + (
            b";" + base64.b64encode(payload) if payload else b"") + b"\x1b\\"

    def picture(width=20, height=20, **kw):
        fields = {"a": "T", "f": 24, "i": 1, "s": width, "v": height, **kw}
        data = bytes((255, 0, 0)) * width * height
        return command(",".join(f"{k}={v}" for k, v in fields.items()), data)

    save()
    with env_for_python_tests():
        # Run upstream's own focused fixtures before drawing conclusions from
        # our observations. They use the same compiled model independently of
        # Nemoterm and cover layout, offsets, layer order and scrolling.
        names = ("test_image_put", "test_graphics_put_with_pixel_offsets",
                 "test_image_layer_grouping", "test_gr_scroll")
        suite = unittest.TestSuite(TestGraphics(name) for name in names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        record["upstream_tests"] = {
            "names": list(names), "run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "successful": result.wasSuccessful(),
        }
        save()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError("Upstream reference fixtures did not all pass")

        layouts = (
            ("natural-one-cell", 10, 20, {}, (0, 0)),
            ("natural-two-by-three", 20, 60, {}, (2, 1)),
            ("both-axes-different-aspect", 40, 20, {"c": 2, "r": 3}, (0, 0)),
            ("columns-only", 20, 40, {"c": 3}, (0, 0)),
            ("rows-only", 20, 20, {"r": 3}, (0, 0)),
            ("native-pixel-offset", 10, 20, {"X": 5, "Y": 5}, (0, 0)),
            ("both-axes-pixel-offset", 40, 20, {"c": 3, "r": 2, "X": 3, "Y": 5}, (1, 1)),
            ("columns-pixel-offset", 40, 20, {"c": 3, "X": 3, "Y": 5}, (1, 1)),
            ("rows-pixel-offset", 40, 20, {"r": 3, "X": 3, "Y": 5}, (1, 1)),
            ("clamped-pixel-offset", 10, 20, {"X": 17, "Y": 29}, (0, 0)),
            ("crop-and-resize", 40, 40, {"x": 3, "y": 5, "w": 12, "h": 18, "c": 4, "r": 2}, (0, 0)),
            ("no-cursor-movement", 20, 60, {"C": 1}, (2, 1)),
            ("right-edge-wrap", 20, 40, {}, (11, 1)),
            ("bottom-scroll", 20, 60, {}, (2, 7)),
        )
        for name, w, h, kw, start in layouts:
            capture(name, [("transmit-and-place", picture(w, h, **kw))], start)

        for name, erase in (
            ("text-overwrite", b"plain text"), ("erase-line", b"\x1b[K"),
            ("erase-entire-line", b"\x1b[2K"), ("erase-below", b"\x1b[J"),
            ("erase-above", b"\x1b[1J"), ("erase-display", b"\x1b[2J"),
            ("erase-history", b"\x1b[3J"), ("reset", b"\x1bc"),
            ("alternate-screen", b"\x1b[?1049h"),
        ):
            capture(name, [("place", picture(C=1)), (name, erase)])

        capture("replace-named-placement", [
            ("place", picture(p=7, C=1)),
            ("move-same-placement", b"\x1b[3;4H" + command("a=p,i=1,p=7,C=1")),
            ("another-placement", b"\x1b[5;7H" + command("a=p,i=1,p=8,C=1")),
            ("remove-first-placement", command("a=d,d=i,i=1,p=7")),
            ("remove-final-and-data", command("a=d,d=I,i=1,p=8")),
        ])
        capture("anonymous-placement-ids", [
            ("place", picture(C=1)),
            ("second-placement", b"\x1b[3;4H" + command("a=p,i=1,C=1")),
            ("remove-visible-keep-data", command("a=d,d=a")),
            ("place-retained-data", command("a=p,i=1,C=1")),
        ])
        capture("layer-order", [
            ("positive", picture(i=3, z=1, C=1)),
            ("negative", picture(i=2, z=-1, C=1)),
            ("below-background", picture(i=1, z=-1073741825, C=1)),
            ("same-z-higher-id", picture(i=4, z=1, C=1)),
        ])
        for name, row, height in (("inside-scroll-region", 1, 40),
                                  ("overlap-top-scroll-region", 0, 40),
                                  ("overlap-bottom-scroll-region", 3, 60)):
            capture(name, [
                ("set-margins-and-place", b"\x1b[2;5r" + f"\x1b[{row+1};1H".encode() + picture(10, height, C=1)),
                ("scroll-one-row", b"\x1b[5;1H\n"),
                ("reverse-one-row", b"\x1b[2;1H\x1bM"),
            ])

        # Additional owner-state inputs isolate gaps in the first capture.
        # These retain raw outcomes without asserting Nemoterm's answers.
        for selector in ("a", "A"):
            capture("delete-below-viewport-" + selector, [
                ("place-at-bottom", b"\x1b[8;1H" + picture(10, 20, C=1)),
                ("reverse-scroll-below", b"\x1b[H\x1bM"),
                ("delete", command("a=d,d=" + selector)),
                ("scroll-back-into-view", b"\x1b[8;1H\n"),
            ])
        capture("delete-visible-preserves-history", [
            ("place-at-top", picture(10, 20, C=1)),
            ("scroll-into-history", b"\x1b[8;1H\n"),
            ("place-visible", b"\x1b[H" + picture(10, 20, i=2, C=1)),
            ("delete-visible-and-data", command("a=d,d=A")),
        ], layer_scrollback=1)
        capture("same-z-reversed-client-ids", [
            ("higher-id-first", picture(10, 20, i=9, z=1, C=1)),
            ("lower-id-second", b"\x1b[3;4H" + picture(10, 20, i=2, z=1, C=1)),
        ])
        for selector, arguments in (("p", "x=2,y=2"), ("q", "x=2,y=2,z=7"),
                                    ("x", "x=2"), ("y", "y=2"), ("z", "z=7")):
            capture("delete-cell-footprint-" + selector, [
                ("offset-positive-layer", picture(10, 20, i=1, X=5, Y=10, z=7, C=1)),
                ("offset-negative-layer", picture(10, 20, i=2, X=5, Y=10, z=-1, C=1)),
                ("delete", command("a=d,d=" + selector + "," + arguments)),
            ], start=(1, 1))
        capture("delete-range-unplaced", [
            ("load-first", picture(10, 20, a="t", i=3)),
            ("load-second", picture(10, 20, a="t", i=5)),
            ("delete-first-range", command("a=d,d=R,x=2,y=4")),
            ("delete-second-range", command("a=d,d=R,x=5,y=6")),
        ])
        capture("delete-newest-number", [
            ("number-first", picture(10, 20, i=0, I=77, C=1)),
            ("number-second", b"\x1b[3;4H" + picture(10, 20, i=0, I=77, C=1)),
            ("delete-newest", command("a=d,d=N,I=77")),
            ("delete-older", command("a=d,d=N,I=77")),
        ])
        capture("retransmission-drops-placements", [
            ("first-image", picture(10, 20, i=1, p=7, C=1)),
            ("second-placement", b"\x1b[3;4H" + command("a=p,i=1,p=8,C=1")),
            ("reload-data", picture(20, 40, a="t", i=1)),
            ("place-reloaded-data", command("a=p,i=1,p=7,C=1")),
        ])
        for direction in ("up", "down"):
            row=1 if direction=="up" else 3
            scroll=b"\x1b[5;1H\n" if direction=="up" else b"\x1b[2;1H\x1bM"
            capture("scaled-offset-clip-" + direction, [
                ("place", b"\x1b[2;5r" + f"\x1b[{row+1};2H".encode() +
                 picture(40, 80, c=2, r=2, X=3, Y=5, C=1)),
                ("clip-one-row", scroll),
                ("remove-last-row", scroll),
            ])

    record["status"] = "complete"
    record["case_count"] = len(record["cases"])
    record["state_count"] = sum(len(c["steps"]) for c in record["cases"])
    save()
    print(f"Completed kitty reference: {record['case_count']} cases, {record['state_count']} states", flush=True)


if __name__ == "__main__":
    main()
