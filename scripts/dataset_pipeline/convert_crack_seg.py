"""
Converts Ultralytics crack-seg polygon annotations to standard YOLO detection bounding boxes.
Preserves original annotations and generates a clean, single-class (0: crack) detection dataset.
"""
from pathlib import Path
from typing import Any

def polygon_to_bbox(coords: list[float]) -> tuple[float, float, float, float] | None:
    """
    Convert a list of normalized polygon coordinates [x1, y1, x2, y2, ...]
    into normalized YOLO bounding box [x_center, y_center, width, height].
    
    Returns None if fewer than 3 coordinate pairs or degenerate dimensions.
    """
    if len(coords) < 6 or len(coords) % 2 != 0:
        return None

    xs = coords[0::2]
    ys = coords[1::2]

    x_min = max(0.0, min(1.0, min(xs)))
    x_max = max(0.0, min(1.0, max(xs)))
    y_min = max(0.0, min(1.0, min(ys)))
    y_max = max(0.0, min(1.0, max(ys)))

    width = x_max - x_min
    height = y_max - y_min

    # Reject degenerate zero-area bounding boxes
    if width <= 1e-5 or height <= 1e-5:
        return None

    x_center = x_min + (width / 2.0)
    y_center = y_min + (height / 2.0)

    return (
        round(x_center, 6),
        round(y_center, 6),
        round(width, 6),
        round(height, 6),
    )


def convert_label_file(src_path: Path, dst_path: Path) -> dict[str, Any]:
    """
    Convert a single polygon label file to standard YOLO detection format.
    Handles multiple polygon lines and preserves 0-byte negative sample files.
    """
    stats = {"total_lines": 0, "valid_boxes": 0, "discarded_lines": 0, "is_negative": False}

    if not src_path.is_file():
        stats["is_negative"] = True
        dst_path.write_text("", encoding="utf-8")
        return stats

    content = src_path.read_text(encoding="utf-8").strip()
    if not content:
        stats["is_negative"] = True
        dst_path.write_text("", encoding="utf-8")
        return stats

    dst_lines: list[str] = []
    for line in content.splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        stats["total_lines"] += 1

        try:
            # Map any source crack class to 0
            coords = [float(v) for v in tokens[1:]]
        except ValueError:
            stats["discarded_lines"] += 1
            continue

        box = polygon_to_bbox(coords)
        if box is not None:
            xc, yc, w, h = box
            dst_lines.append(f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
            stats["valid_boxes"] += 1
        else:
            stats["discarded_lines"] += 1

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text("\n".join(dst_lines) + ("\n" if dst_lines else ""), encoding="utf-8")
    return stats
