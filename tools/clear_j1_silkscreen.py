"""Subtract J1's JLCPCB silkscreen-clearance region from decorative artwork.

The script derives the 2x20 header pad centers from footprint J1, creates one
User.1 polygon per pad at the pad edge plus 0.15 mm, and subtracts their union
from F.SilkS fp_poly objects in PCBDrawings:* footprints.  Its generated UUIDs
are deterministic, so the helper geometry is easy to identify and reruns are
safe.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import re
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from clip_pcbdrawings_silkscreen import (
    BOOLEAN_SCALE,
    INKSCAPE_DEFAULT,
    NUMBER,
    inverse_transform,
    make_fp_poly,
    nested_forms,
    parse_svg_path,
    point_inside,
    points,
    segments_cross,
    signed_area,
    svg_path,
    transform,
)


CLEARANCE_MM = 0.15
CIRCLE_VERTICES = 64
UUID_NAMESPACE = uuid.UUID("f28bfdf6-8891-41e0-a64b-805412227afd")


@dataclass
class PadKeepout:
    number: str
    polygon: list[tuple[float, float]]
    object_uuid: str


@dataclass
class Candidate:
    footprint: str
    source_form: str
    source_uuid: str
    origin_x: float
    origin_y: float
    angle: float
    art_id: str


def placement(form: str) -> tuple[float, float, float]:
    match = re.search(
        rf"^\s*\(at\s+({NUMBER})\s+({NUMBER})(?:\s+({NUMBER}))?\)",
        form,
        re.MULTILINE,
    )
    if not match:
        raise SystemExit("Could not parse an object placement")
    return float(match.group(1)), float(match.group(2)), math.radians(float(match.group(3) or 0))


def footprint_to_board(
    point: tuple[float, float], origin_x: float, origin_y: float, angle: float, flipped: bool
) -> tuple[float, float]:
    x, y = point
    if flipped:
        # KiCad stores a back-side footprint's local coordinates in its
        # mirrored frame.  For J1 this maps local (0, -2.54) to board
        # (-2.54, 0) at a displayed rotation of 90 degrees.
        angle = -angle
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return origin_x + cosine * x - sine * y, origin_y + sine * x + cosine * y


def make_circle(center: tuple[float, float], radius: float) -> list[tuple[float, float]]:
    # Circumscribed polygon: every edge, not merely every vertex, is at least
    # radius from the pad center.
    vertex_radius = radius / math.cos(math.pi / CIRCLE_VERTICES)
    return [
        (
            center[0] + vertex_radius * math.cos(2 * math.pi * index / CIRCLE_VERTICES),
            center[1] + vertex_radius * math.sin(2 * math.pi * index / CIRCLE_VERTICES),
        )
        for index in range(CIRCLE_VERTICES)
    ]


def make_square(center: tuple[float, float], half_size: float) -> list[tuple[float, float]]:
    x, y = center
    return [
        (x - half_size, y - half_size),
        (x + half_size, y - half_size),
        (x + half_size, y + half_size),
        (x - half_size, y + half_size),
    ]


def j1_keepouts(root_forms: list[str]) -> list[PadKeepout]:
    matches = [form for form in root_forms if form.startswith("(footprint") and '(property "Reference" "J1"' in form]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one J1 footprint; found {len(matches)}")
    footprint = matches[0]
    origin_x, origin_y, angle = placement(footprint)
    flipped = '(layer "B.Cu")' in footprint
    result: list[PadKeepout] = []
    for pad in nested_forms(footprint, 2):
        pad_match = re.match(r'\(pad "([^"]+)"\s+\S+\s+(\S+)', pad)
        if not pad_match or '"*.Mask"' not in pad:
            continue
        number, shape = pad_match.groups()
        size_match = re.search(rf"\(size\s+({NUMBER})\s+({NUMBER})\)", pad)
        if not size_match:
            raise SystemExit(f"J1 pad {number} has no parseable size")
        width, height = float(size_match.group(1)), float(size_match.group(2))
        if abs(width - height) > 1e-9:
            raise SystemExit(f"J1 pad {number} is not symmetric; unsupported size {width}x{height}")
        local_x, local_y, _ = placement(pad)
        center = footprint_to_board((local_x, local_y), origin_x, origin_y, angle, flipped)
        half_size = width / 2 + CLEARANCE_MM
        if shape == "circle":
            polygon = make_circle(center, half_size)
        elif shape == "rect":
            polygon = make_square(center, half_size)
        else:
            raise SystemExit(f"J1 pad {number} has unsupported shape {shape}")
        result.append(
            PadKeepout(
                number=number,
                polygon=polygon,
                object_uuid=str(uuid.uuid5(UUID_NAMESPACE, f"J1-pad-{number}-silk-clearance-{CLEARANCE_MM:.2f}")),
            )
        )
    if len(result) != 40:
        raise SystemExit(f"Expected 40 mask-bearing J1 pads; found {len(result)}")
    return result


def bbox(poly: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in poly]
    ys = [point[1] for point in poly]
    return min(xs), min(ys), max(xs), max(ys)


def bboxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def make_gr_poly(poly: list[tuple[float, float]], object_uuid: str) -> str:
    rows = ["\t(gr_poly", "\t\t(pts"]
    rows.extend(f"\t\t\t(xy {x:.6f} {y:.6f})" for x, y in poly)
    rows.extend(
        [
            "\t\t)",
            "\t\t(stroke",
            "\t\t\t(width 0)",
            "\t\t\t(type solid)",
            "\t\t)",
            "\t\t(fill solid)",
            '\t\t(layer "User.1")',
            f'\t\t(uuid "{object_uuid}")',
            "\t)",
        ]
    )
    return "\n".join(rows)


def bridge_compound(
    contours: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Encode holes as doubled, non-crossing bridges in ordinary polygons."""
    dominant = max(contours, key=lambda contour: abs(signed_area(contour)))
    outer_sign = 1 if signed_area(dominant) > 0 else -1
    outers = [contour[:] for contour in contours if signed_area(contour) * outer_sign > 0]
    holes = [contour[:] for contour in contours if signed_area(contour) * outer_sign < 0]
    original_boundaries = [
        (contour[index], contour[(index + 1) % len(contour)])
        for contour in contours
        for index in range(len(contour))
    ]
    assigned: list[list[list[tuple[float, float]]]] = [[] for _ in outers]
    for hole in holes:
        owners = [
            (abs(signed_area(outer)), index)
            for index, outer in enumerate(outers)
            if point_inside(hole[0], outer)
        ]
        if not owners:
            raise SystemExit("Could not assign an SVG hole to an outer contour")
        assigned[min(owners)[1]].append(hole)

    result: list[list[tuple[float, float]]] = []
    for outer, outer_holes in zip(outers, assigned):
        original_outer = outer[:]
        bridges: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for hole in outer_holes:
            hole_index = max(range(len(hole)), key=lambda index: (hole[index][0], -hole[index][1]))
            hole_point = hole[hole_index]
            candidates: list[tuple[float, int]] = []
            for outer_index, outer_point in enumerate(original_outer):
                samples = [
                    (
                        hole_point[0] + fraction * (outer_point[0] - hole_point[0]),
                        hole_point[1] + fraction * (outer_point[1] - hole_point[1]),
                    )
                    for fraction in (0.1, 0.25, 0.5, 0.75, 0.9)
                ]
                if not all(point_inside(sample, original_outer) for sample in samples):
                    continue
                if any(point_inside(sample, other) for other in outer_holes for sample in samples):
                    continue
                if any(
                    segments_cross(hole_point, outer_point, start, end)
                    for start, end in original_boundaries + bridges
                ):
                    continue
                candidates.append((math.dist(hole_point, outer_point), outer_index))
            if not candidates:
                raise SystemExit("Could not find a non-crossing bridge for an SVG hole")
            _, original_index = min(candidates)
            outer_point = original_outer[original_index]
            # Locate this original vertex in the progressively bridged contour.
            outer_index = next(
                index for index, point in enumerate(outer) if point == outer_point
            )
            hole_cycle = hole[hole_index:] + hole[: hole_index + 1]
            outer = (
                outer[: outer_index + 1]
                + [hole_point]
                + hole_cycle[1:]
                + [outer_point]
                + outer[outer_index + 1 :]
            )
            bridges.append((hole_point, outer_point))

        expected_area = abs(
            signed_area(original_outer) + sum(signed_area(hole) for hole in outer_holes)
        )
        actual_area = abs(signed_area(outer))
        if abs(actual_area - expected_area) > max(1.0, expected_area) * 1e-8:
            raise SystemExit("Hole bridging changed the filled polygon area")
        result.append(outer)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    parser.add_argument("--inkscape", type=Path, default=INKSCAPE_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--debug-dir", type=Path)
    parser.add_argument(
        "--remove-helpers",
        action="store_true",
        help="remove this script's J1 User.1 polygons without changing the clipped silk",
    )
    args = parser.parse_args()

    board_text = args.board.read_text(encoding="utf-8")
    root_forms = nested_forms(board_text, 2)
    keepouts = j1_keepouts(root_forms)
    if args.remove_helpers:
        new_board_text = board_text
        removed = 0
        helper_uuids = {item.object_uuid for item in keepouts}
        for form in root_forms:
            if not form.startswith("(gr_poly"):
                continue
            uuid_match = re.search(r'\(uuid "([^"]+)"\)', form)
            if not uuid_match or uuid_match.group(1) not in helper_uuids:
                continue
            if new_board_text.count("\t" + form) != 1:
                raise SystemExit("Could not uniquely locate a J1 User.1 helper")
            new_board_text = new_board_text.replace("\t" + form + "\n", "", 1)
            removed += 1
        if removed and not args.dry_run:
            with args.board.open("w", encoding="utf-8", newline="\n") as board_file:
                board_file.write(new_board_text)
        print(f"{'Would remove' if args.dry_run else 'Removed'} {removed} J1 User.1 helpers.")
        return
    keepout_boxes = [bbox(item.polygon) for item in keepouts]
    compound_keepout = " ".join(svg_path(item.polygon) for item in keepouts)
    candidates: list[Candidate] = []
    svg_elements: list[str] = []
    action_steps: list[str] = []

    for footprint in root_forms:
        name_match = re.match(r'\(footprint "([^"]+)"', footprint)
        if not name_match or not name_match.group(1).startswith("PCBDrawings:"):
            continue
        origin_x, origin_y, angle = placement(footprint)
        for poly_form in nested_forms(footprint, 2):
            if not poly_form.startswith("(fp_poly") or '(layer "F.SilkS")' not in poly_form:
                continue
            global_poly = transform(points(poly_form), origin_x, origin_y, angle)
            global_box = bbox(global_poly)
            if not any(bboxes_overlap(global_box, keepout_box) for keepout_box in keepout_boxes):
                continue
            object_index = len(candidates)
            art_id = f"art{object_index}"
            keepout_id = f"keepout{object_index}"
            uuid_match = re.search(r'\(uuid "([^"]+)"\)', poly_form)
            if not uuid_match:
                raise SystemExit("An fp_poly is missing its UUID")
            candidates.append(
                Candidate(name_match.group(1), poly_form, uuid_match.group(1), origin_x, origin_y, angle, art_id)
            )
            svg_elements.append(f'<path id="{art_id}" d="{svg_path(global_poly)}"/>')
            svg_elements.append(f'<path id="{keepout_id}" d="{compound_keepout}"/>')
            action_steps.extend([f"select-by-id:{art_id},{keepout_id}", "path-difference", "select-clear"])

    if not args.inkscape.exists():
        raise SystemExit(f"Inkscape not found at {args.inkscape}")
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220000 180000">' + "".join(svg_elements) + "</svg>"
    if args.debug_dir:
        args.debug_dir.mkdir(parents=True, exist_ok=True)
        workspace = contextlib.nullcontext(str(args.debug_dir))
    else:
        workspace = tempfile.TemporaryDirectory(prefix="kicad-j1-silk-clearance-")
    with workspace as temp_dir:
        input_svg = Path(temp_dir) / "input.svg"
        output_svg = Path(temp_dir) / "output.svg"
        input_svg.write_text(svg, encoding="utf-8")
        actions = ";".join(action_steps + [f"export-filename:{output_svg}", "export-do"])
        result = subprocess.run(
            [str(args.inkscape), str(input_svg), "--batch-process", f"--actions={actions}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if result.returncode != 0 or not output_svg.exists():
            raise SystemExit(f"Inkscape subtraction failed ({result.returncode}):\n{result.stderr}")
        svg_root = ET.parse(output_svg).getroot()
        result_paths = {
            element.attrib["id"]: element.attrib.get("d", "")
            for element in svg_root.iter()
            if element.tag.endswith("path") and "id" in element.attrib
        }

    replacements: list[tuple[str, str]] = []
    hole_results = 0
    bridged_polygons = 0
    changed = 0
    for candidate in candidates:
        result_global = parse_svg_path(result_paths.get(candidate.art_id, ""))
        areas = [signed_area(poly) for poly in result_global]
        if areas and any(area * areas[0] < 0 for area in areas[1:]):
            hole_results += 1
            result_global = bridge_compound(result_global)
            bridged_polygons += len(result_global)
        result_local = [
            inverse_transform(
                [(x / BOOLEAN_SCALE, y / BOOLEAN_SCALE) for x, y in poly],
                candidate.origin_x,
                candidate.origin_y,
                candidate.angle,
            )
            for poly in result_global
        ]
        replacement_forms = [
            make_fp_poly(poly, candidate.source_uuid if index == 0 else str(uuid.uuid4()))
            for index, poly in enumerate(result_local)
            if len(poly) >= 3 and abs(signed_area(poly)) > 1e-9
        ]
        replacement = "\n\t\t".join(replacement_forms)
        if replacement != candidate.source_form:
            changed += 1
        replacements.append((candidate.source_form, replacement))

    print(
        f"J1 keepout: {len(keepouts)} polygons; candidates: {len(candidates)}; "
        f"changed results: {changed}; decomposed compounds: {hole_results} "
        f"({bridged_polygons} bridged polygons)."
    )
    if args.dry_run:
        return

    new_board_text = board_text
    for source, replacement in replacements:
        indented_source = "\t\t" + source
        indented_replacement = "\t\t" + replacement if replacement else ""
        if new_board_text.count(indented_source) != 1:
            raise SystemExit("Could not uniquely locate an original fp_poly during replacement")
        new_board_text = new_board_text.replace(indented_source, indented_replacement, 1)

    missing_helpers: list[PadKeepout] = []
    for item in keepouts:
        existing = next(
            (
                form
                for form in nested_forms(new_board_text, 2)
                if form.startswith("(gr_poly") and f'(uuid "{item.object_uuid}")' in form
            ),
            None,
        )
        if existing is None:
            missing_helpers.append(item)
            continue
        replacement = make_gr_poly(item.polygon, item.object_uuid).removeprefix("\t")
        if new_board_text.count("\t" + existing) != 1:
            raise SystemExit(f"Could not uniquely locate J1 helper {item.number}")
        new_board_text = new_board_text.replace("\t" + existing, "\t" + replacement, 1)
    if missing_helpers:
        marker = "\t(embedded_fonts no)\n)"
        if new_board_text.count(marker) != 1:
            raise SystemExit("Could not locate the board-level insertion point")
        helpers_text = "\n".join(make_gr_poly(item.polygon, item.object_uuid) for item in missing_helpers)
        new_board_text = new_board_text.replace(marker, helpers_text + "\n" + marker, 1)

    if new_board_text == board_text:
        print("No board changes were required.")
        return
    with args.board.open("w", encoding="utf-8", newline="\n") as board_file:
        board_file.write(new_board_text)
    print(
        f"Updated 40 User.1 pad helpers ({len(missing_helpers)} new) and "
        f"clipped {changed} decorative polygons."
    )


if __name__ == "__main__":
    main()
