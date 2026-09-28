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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        """Reconstructs BoundingBox from serialized dictionary representation."""
        x0 = float(data.get("x0", 0.0))
        y0 = float(data.get("y0", 0.0))
        x1 = float(data.get("x1", 0.0))
        y1 = float(data.get("y1", 0.0))
        angle = float(data.get("angle", 0.0))
        raw_quad = data.get("quad")
        quad: Optional[List[List[float]]] = None
        if raw_quad is not None and isinstance(raw_quad, list):
            quad = [[float(pt[0]), float(pt[1])] for pt in raw_quad if len(pt) >= 2]
        return cls(x0=x0, y0=y0, x1=x1, y1=y1, angle=angle, quad=quad)

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
