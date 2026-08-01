"""Clip decorative KiCad footprint silkscreen polygons to a board helper polygon.

The board must contain exactly one filled gr_poly on User.1.  That polygon is
treated as the allowed silkscreen area.  Only F.SilkS fp_poly objects inside
PCBDrawings:* footprints are modified.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


INKSCAPE_DEFAULT = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
XY_RE = re.compile(rf"\(xy\s+({NUMBER})\s+({NUMBER})\)")
PATH_TOKEN_RE = re.compile(rf"[MmLlHhVvZz]|{NUMBER}")
GEOMETRY_EPSILON = 1e-5
BOOLEAN_SCALE = 1000.0


@dataclass
class Candidate:
    footprint: str
    source_form: str
    source_uuid: str
    origin_x: float
    origin_y: float
    angle: float
    art_id: str
    clip_id: str


def nested_forms(text: str, target_depth: int) -> list[str]:
    result: list[str] = []
    depth = 0
    start: int | None = None
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
            if depth == target_depth:
                start = index
        elif char == ")":
            if depth == target_depth and start is not None:
                result.append(text[start : index + 1])
                start = None
            depth -= 1
    return result


def points(form: str) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in XY_RE.findall(form)]


def signed_area(poly: list[tuple[float, float]]) -> float:
    return sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))
    ) / 2


def cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def distance_to_segment(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.dist(point, a)
    position = max(
        0.0,
        min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_squared),
    )
    projection = (a[0] + position * dx, a[1] + position * dy)
    return math.dist(point, projection)


def point_inside(point: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    for i, a in enumerate(poly):
        if distance_to_segment(point, a, poly[(i + 1) % len(poly)]) <= GEOMETRY_EPSILON:
            return True
    x, y = point
    inside = False
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        if (a[1] > y) != (b[1] > y):
            crossing_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < crossing_x:
                inside = not inside
    return inside


def segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    return cross(a, b, c) * cross(a, b, d) < -1e-12 and cross(c, d, a) * cross(c, d, b) < -1e-12


def safely_inside(subject: list[tuple[float, float]], clip: list[tuple[float, float]]) -> bool:
    for i, a in enumerate(subject):
        b = subject[(i + 1) % len(subject)]
        for fraction in (0.0, 0.25, 0.5, 0.75):
            sample = (
                a[0] + fraction * (b[0] - a[0]),
                a[1] + fraction * (b[1] - a[1]),
            )
            if not point_inside(sample, clip):
                return False
    return True


def transform(
    poly: list[tuple[float, float]], origin_x: float, origin_y: float, angle: float
) -> list[tuple[float, float]]:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return [
        (origin_x + cosine * x - sine * y, origin_y + sine * x + cosine * y)
        for x, y in poly
    ]


def inverse_transform(
    poly: list[tuple[float, float]], origin_x: float, origin_y: float, angle: float
) -> list[tuple[float, float]]:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return [
        (cosine * (x - origin_x) + sine * (y - origin_y), -sine * (x - origin_x) + cosine * (y - origin_y))
        for x, y in poly
    ]


def svg_path(poly: list[tuple[float, float]]) -> str:
    scaled = [(x * BOOLEAN_SCALE, y * BOOLEAN_SCALE) for x, y in poly]
    coords = " ".join(f"L {x:.9f} {y:.9f}" for x, y in scaled[1:])
    return f"M {scaled[0][0]:.9f} {scaled[0][1]:.9f} {coords} Z"


def parse_svg_path(data: str) -> list[list[tuple[float, float]]]:
    tokens = PATH_TOKEN_RE.findall(data.replace(",", " "))
    paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    command: str | None = None
    index = 0

    def number(token: str) -> bool:
        return not token.isalpha()

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command in "Zz":
                if current:
                    if math.dist(current[0], current[-1]) < 1e-7:
                        current.pop()
                    if len(current) >= 3 and abs(signed_area(current)) > 1e-10:
                        paths.append(current)
                    current = []
                continue
        if command is None:
            raise ValueError(f"SVG path has data without a command: {data}")
        if command in "MmLl":
            if index + 1 >= len(tokens) or not number(tokens[index]) or not number(tokens[index + 1]):
                raise ValueError(f"Malformed SVG coordinate pair: {data}")
            x = float(tokens[index])
            y = float(tokens[index + 1])
            index += 2
            if command.islower():
                x += cursor[0]
                y += cursor[1]
            cursor = (x, y)
            if command in "Mm":
                if current:
                    if math.dist(current[0], current[-1]) < 1e-7:
                        current.pop()
                    if len(current) >= 3 and abs(signed_area(current)) > 1e-10:
                        paths.append(current)
                current = [cursor]
                command = "l" if command == "m" else "L"
            else:
                current.append(cursor)
        elif command in "Hh":
            x = float(tokens[index])
            index += 1
            if command == "h":
                x += cursor[0]
            cursor = (x, cursor[1])
            current.append(cursor)
        elif command in "Vv":
            y = float(tokens[index])
            index += 1
            if command == "v":
                y += cursor[1]
            cursor = (cursor[0], y)
            current.append(cursor)
        else:
            raise ValueError(f"Unexpected curved SVG command {command!r}; polygonal output was expected")
    if current:
        if math.dist(current[0], current[-1]) < 1e-7:
            current.pop()
        if len(current) >= 3 and abs(signed_area(current)) > 1e-10:
            paths.append(current)
    return paths


def make_fp_poly(poly: list[tuple[float, float]], object_uuid: str) -> str:
    rows = ["(fp_poly", "\t\t\t(pts"]
    rows.extend(f"\t\t\t\t(xy {x:.6f} {y:.6f})" for x, y in poly)
    rows.extend(
        [
            "\t\t\t)",
            "\t\t\t(stroke",
            "\t\t\t\t(width 0)",
            "\t\t\t\t(type solid)",
            "\t\t\t)",
            "\t\t\t(fill yes)",
            '\t\t\t(layer "F.SilkS")',
            f'\t\t\t(uuid "{object_uuid}")',
            "\t\t)",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    parser.add_argument("--inkscape", type=Path, default=INKSCAPE_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    board_text = args.board.read_text(encoding="utf-8")
    root_forms = nested_forms(board_text, 2)
    helpers = [
        form
        for form in root_forms
        if form.startswith("(gr_poly") and '(layer "User.1")' in form
    ]
    if len(helpers) != 1:
        raise SystemExit(f"Expected exactly one User.1 gr_poly helper; found {len(helpers)}")
    clip = points(helpers[0])
    if len(clip) < 3:
        raise SystemExit("User.1 helper polygon is empty")
    if not args.inkscape.exists():
        raise SystemExit(f"Inkscape not found at {args.inkscape}")

    candidates: list[Candidate] = []
    svg_elements: list[str] = []
    action_steps: list[str] = []
    for footprint_form in root_forms:
        name_match = re.match(r'\(footprint "([^"]+)"', footprint_form)
        if not name_match or not name_match.group(1).startswith("PCBDrawings:"):
            continue
        at_match = re.search(
            rf"^\s*\(at\s+({NUMBER})\s+({NUMBER})(?:\s+({NUMBER}))?\)",
            footprint_form,
            re.MULTILINE,
        )
        if not at_match:
            raise SystemExit(f"Could not parse placement for {name_match.group(1)}")
        origin_x = float(at_match.group(1))
        origin_y = float(at_match.group(2))
        angle = math.radians(float(at_match.group(3) or 0))
        for poly_form in nested_forms(footprint_form, 2):
            if not poly_form.startswith("(fp_poly") or '(layer "F.SilkS")' not in poly_form:
                continue
            global_poly = transform(points(poly_form), origin_x, origin_y, angle)
            if safely_inside(global_poly, clip):
                continue
            object_index = len(candidates)
            art_id = f"art{object_index}"
            clip_id = f"clip{object_index}"
            uuid_match = re.search(r'\(uuid "([^"]+)"\)', poly_form)
            if not uuid_match:
                raise SystemExit("An fp_poly is missing its UUID")
            candidates.append(
                Candidate(
                    footprint=name_match.group(1),
                    source_form=poly_form,
                    source_uuid=uuid_match.group(1),
                    origin_x=origin_x,
                    origin_y=origin_y,
                    angle=angle,
                    art_id=art_id,
                    clip_id=clip_id,
                )
            )
            svg_elements.append(f'<path id="{art_id}" d="{svg_path(global_poly)}"/>')
            svg_elements.append(f'<path id="{clip_id}" d="{svg_path(clip)}"/>')
            action_steps.extend(
                [f"select-by-id:{art_id},{clip_id}", "path-intersection", "select-clear"]
            )

    if not candidates:
        print("No decorative silkscreen polygons require clipping.")
        return
    if args.dry_run:
        print(f"{len(candidates)} decorative silkscreen polygons require clipping.")
        return

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 220000 180000">'
        + "".join(svg_elements)
        + "</svg>"
    )
    with tempfile.TemporaryDirectory(prefix="kicad-silk-clip-") as temp_dir:
        input_svg = Path(temp_dir) / "input.svg"
        output_svg = Path(temp_dir) / "output.svg"
        input_svg.write_text(svg, encoding="utf-8")
        actions = ";".join(
            action_steps + [f"export-filename:{output_svg}", "export-do"]
        )
        result = subprocess.run(
            [
                str(args.inkscape),
                str(input_svg),
                "--batch-process",
                f"--actions={actions}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if result.returncode != 0 or not output_svg.exists():
            raise SystemExit(
                f"Inkscape clipping failed ({result.returncode}):\n{result.stderr}"
            )
        svg_root = ET.parse(output_svg).getroot()
        result_paths = {
            element.attrib["id"]: element.attrib.get("d", "")
            for element in svg_root.iter()
            if element.tag.endswith("path") and "id" in element.attrib
        }

    replacements: list[tuple[str, str]] = []
    removed = 0
    created = 0
    for candidate in candidates:
        clipped_global = parse_svg_path(result_paths.get(candidate.art_id, ""))
        clipped_global = [
            [(x / BOOLEAN_SCALE, y / BOOLEAN_SCALE) for x, y in poly]
            for poly in clipped_global
        ]
        clipped_local = [
            inverse_transform(
                poly,
                candidate.origin_x,
                candidate.origin_y,
                candidate.angle,
            )
            for poly in clipped_global
        ]
        replacement_forms: list[str] = []
        for index, poly in enumerate(clipped_local):
            if len(poly) < 3 or abs(signed_area(poly)) < 1e-9:
                continue
            object_uuid = candidate.source_uuid if index == 0 else str(uuid.uuid4())
            replacement_forms.append(make_fp_poly(poly, object_uuid))
        if not replacement_forms:
            removed += 1
        created += len(replacement_forms)
        replacements.append((candidate.source_form, "\n\t\t".join(replacement_forms)))

    new_board_text = board_text
    for source, replacement in replacements:
        indented_source = "\t\t" + source
        indented_replacement = "\t\t" + replacement if replacement else ""
        if new_board_text.count(indented_source) != 1:
            raise SystemExit("Could not uniquely locate an original fp_poly during replacement")
        new_board_text = new_board_text.replace(indented_source, indented_replacement, 1)

    if new_board_text == board_text:
        raise SystemExit("Clipping produced no board changes")
    with args.board.open("w", encoding="utf-8", newline="\n") as board_file:
        board_file.write(new_board_text)
    print(
        f"Clipped {len(candidates)} decorative fp_poly objects: "
        f"removed {removed}, wrote {created} result polygons."
    )


if __name__ == "__main__":
    main()
