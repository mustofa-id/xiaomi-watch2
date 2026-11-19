#!/usr/bin/env python3
"""Regenerate the moon-phase icons and date rule in res/drawable-nodpi.

The shapes are generated from geometry (outer circle + terminator ellipse), not
traced, so every phase has the same radius and stroke. WFF's PartImage only
renders bitmap resources on the reference runtime, so the SVGs are rasterised
at the on-screen size (40 px for a 36-unit box, ~37 px on this device).

Requires rsvg-convert (librsvg).
"""
import subprocess
import tempfile
from pathlib import Path

R = 44.0            # outer radius in the 100x100 viewBox
CX = CY = 50.0
A = 22.0            # terminator semi-axis for the 25%/75% phases
STROKE = 5.0
MOON_COLOR = "#E8FFEC"
RULE_COLOR = "#FFFFFF"

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "face/src/main/res/drawable-nodpi"


def phase_path(outer_sweep: int, term_sweep: int | None) -> str:
    top = f"{CX:g},{CY - R:g}"
    bottom = f"{CX:g},{CY + R:g}"
    path = f"M{top} A{R:g},{R:g} 0 0 {outer_sweep} {bottom}"
    if term_sweep is not None:
        path += f" A{A:g},{R:g} 0 0 {term_sweep} {top}"
    return path + " Z"


FULL = (
    f"M{CX:g},{CY - R:g} A{R:g},{R:g} 0 1 1 {CX:g},{CY + R:g} "
    f"A{R:g},{R:g} 0 1 1 {CX:g},{CY - R:g} Z"
)

# name -> lit path (None means new moon: ring only)
PHASES = {
    "new": None,
    "waxing_crescent": phase_path(1, 0),
    "first_quarter": phase_path(1, None),
    "waxing_gibbous": phase_path(1, 1),
    "full": FULL,
    "waning_gibbous": phase_path(0, 0),
    "last_quarter": phase_path(0, None),
    "waning_crescent": phase_path(0, 1),
}

RING = (
    f'<circle cx="{CX:g}" cy="{CY:g}" r="{R - STROKE / 2:g}" '
    f'fill="none" stroke="{MOON_COLOR}" stroke-width="{STROKE:g}"/>'
)

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
    'viewBox="0 0 100 100"><rect width="100" height="100" fill="black"/>{}</svg>'
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for name, lit in PHASES.items():
            body = "" if lit is None else f'<path d="{lit}" fill="{MOON_COLOR}"/>'
            svg = Path(tmp) / f"{name}.svg"
            svg.write_text(SVG.format(body + RING))
            png = OUT / f"moon_{name}.png"
            subprocess.run(
                ["rsvg-convert", "-w", "40", "-h", "40", str(svg), "-o", str(png)],
                check=True,
            )
            print(f"wrote {png.relative_to(ROOT)}")

        separator_svg = Path(tmp) / "date_separator.svg"
        separator_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 31 2">'
            f'<rect width="31" height="2" fill="{RULE_COLOR}"/></svg>'
        )
        separator_png = OUT / "date_separator.png"
        subprocess.run(
            [
                "rsvg-convert",
                "-w",
                "62",
                "-h",
                "4",
                str(separator_svg),
                "-o",
                str(separator_png),
            ],
            check=True,
        )
        print(f"wrote {separator_png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
