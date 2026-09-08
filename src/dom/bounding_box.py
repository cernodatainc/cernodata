"""
src/dom/bounding_box.py

BoundingBox data primitive for geometric coordinates and text alignment rotation angles.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float
    angle: float = 0.0  # Rotation angle in degrees (text alignment orientation)
    quad: Optional[List[List[float]]] = None  # 4 corner vertices: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2)
        }
        if self.angle != 0.0:
            res["angle"] = round(self.angle, 2)
        if self.quad is not None:
            res["quad"] = [[round(p[0], 2), round(p[1], 2)] for p in self.quad]
        return res

    def to_polygon(self, sx: float = 1.0, sy: float = 1.0) -> List[Tuple[float, float]]:
        """
        Computes 4 corner vertices [(x0', y0'), (x1', y1'), (x2', y2'), (x3', y3')]
        scaled by (sx, sy) and rotated around bounding box center by `angle` degrees,
        or scaled from explicit quad vertices if defined.
        """
        if self.quad is not None and len(self.quad) == 4:
            return [(p[0] * sx, p[1] * sy) for p in self.quad]
        scaled_x0 = self.x0 * sx
        scaled_y0 = self.y0 * sy
        scaled_x1 = self.x1 * sx
        scaled_y1 = self.y1 * sy

        # Calculate bounding box center
        cx = (scaled_x0 + scaled_x1) / 2.0
        cy = (scaled_y0 + scaled_y1) / 2.0

        # Unrotated box corner vertices (Top-Left, Top-Right, Bottom-Right, Bottom-Left)
        unrotated_corners = [
            (scaled_x0, scaled_y0),
            (scaled_x1, scaled_y0),
            (scaled_x1, scaled_y1),
            (scaled_x0, scaled_y1)
        ]

        if self.angle == 0.0:
            return unrotated_corners

        rad = math.radians(self.angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        polygon = []
        for px, py in unrotated_corners:
            dx = px - cx
            dy = py - cy
            rx = cx + dx * cos_a - dy * sin_a
            ry = cy + dx * sin_a + dy * cos_a
            polygon.append((rx, ry))

        return polygon
