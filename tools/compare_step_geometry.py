import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path


ENTITY_RE = re.compile(r"#(\d+)\s*=\s*(.*?);", re.DOTALL)
REF_RE = re.compile(r"#(\d+)")
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:E[-+]?\d+)?", re.I)


def split_args(text):
    args, buf, depth, quoted = [], [], 0, False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "'":
            buf.append(c)
            if quoted and i + 1 < len(text) and text[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            quoted = not quoted
        elif not quoted and c == "(":
            depth += 1
            buf.append(c)
        elif not quoted and c == ")":
            depth -= 1
            buf.append(c)
        elif not quoted and depth == 0 and c == ",":
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    args.append("".join(buf).strip())
    return args


def parse_entity(raw):
    match = re.match(r"\s*([A-Z0-9_]+)\s*\((.*)\)\s*$", raw, re.DOTALL)
    if not match:
        return raw.strip(), []
    return match.group(1), split_args(match.group(2))


def ref(arg):
    match = REF_RE.fullmatch(arg.strip())
    return int(match.group(1)) if match else None


def numbers(arg):
    return [float(v) for v in NUMBER_RE.findall(arg)]


def vec_add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def vec_scale(a, s):
    return tuple(x * s for x in a)


def vec_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def vec_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalize(v):
    length = math.sqrt(vec_dot(v, v))
    return tuple(x / length for x in v) if length else (0.0, 0.0, 0.0)


class StepModel:
    def __init__(self, path):
        self.path = Path(path)
        text = self.path.read_text(encoding="utf-8", errors="replace")
        self.entities = {int(n): parse_entity(raw) for n, raw in ENTITY_RE.findall(text)}

    def typed(self, name):
        return ((n, args) for n, (kind, args) in self.entities.items() if kind == name)

    def point(self, n):
        kind, args = self.entities[n]
        assert kind == "CARTESIAN_POINT"
        vals = numbers(args[-1])
        return tuple(vals + [0.0] * (3 - len(vals)))

    def direction(self, n):
        kind, args = self.entities[n]
        assert kind == "DIRECTION"
        vals = numbers(args[-1])
        return normalize(tuple(vals + [0.0] * (3 - len(vals))))

    def axis(self, n):
        kind, args = self.entities[n]
        assert kind == "AXIS2_PLACEMENT_3D"
        origin = self.point(ref(args[1]))
        z = self.direction(ref(args[2])) if len(args) > 2 and ref(args[2]) else (0.0, 0.0, 1.0)
        x = self.direction(ref(args[3])) if len(args) > 3 and ref(args[3]) else (1.0, 0.0, 0.0)
        y = normalize(vec_cross(z, x))
        x = normalize(vec_cross(y, z))
        return origin, x, y, normalize(z)

    def vertices(self):
        result = []
        for _, args in self.typed("VERTEX_POINT"):
            p_ref = ref(args[-1])
            if p_ref:
                result.append(self.point(p_ref))
        return result

    def cylinders(self):
        result = []
        for entity_id, args in self.typed("CYLINDRICAL_SURFACE"):
            placement = ref(args[1])
            radius_vals = numbers(args[2])
            if placement and radius_vals:
                origin, x, y, z = self.axis(placement)
                result.append({"entity": entity_id, "origin": origin, "axis": z, "radius": radius_vals[0]})
        return result

    def circles(self):
        result = []
        for entity_id, args in self.typed("CIRCLE"):
            placement = ref(args[1])
            radius_vals = numbers(args[2])
            if placement and radius_vals:
                origin, x, y, z = self.axis(placement)
                result.append({"entity": entity_id, "origin": origin, "axis": z, "radius": radius_vals[0]})
        return result

    def summary(self):
        vertices = self.vertices()
        bbox = None
        if vertices:
            bbox = {
                "min": [min(p[i] for p in vertices) for i in range(3)],
                "max": [max(p[i] for p in vertices) for i in range(3)],
            }
            bbox["size"] = [bbox["max"][i] - bbox["min"][i] for i in range(3)]
        cylinders = self.cylinders()
        circles = self.circles()
        return {
            "path": str(self.path),
            "entity_count": len(self.entities),
            "vertex_count": len(vertices),
            "vertex_bbox": bbox,
            "cylinder_count": len(cylinders),
            "cylinder_radii": dict(sorted(Counter(round(c["radius"], 6) for c in cylinders).items())),
            "circle_count": len(circles),
            "circle_radii": dict(sorted(Counter(round(c["radius"], 6) for c in circles).items())),
            "cylinders": cylinders,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    print(json.dumps([StepModel(path).summary() for path in args.paths], indent=2))


if __name__ == "__main__":
    main()
