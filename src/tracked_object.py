from dataclasses import dataclass


@dataclass
class Point2D:
    x: int
    y: int


@dataclass
class BoundingBox:
    top_left: Point2D
    bottom_right: Point2D


@dataclass
class DetectedObject:
    """Represents a detected object from a single frame"""

    class_name: str
    confidence: float
    center: Point2D
    bbox: BoundingBox


@dataclass
class TrackerObject:
    """Represents a known tracked object with a known lifetime and persistent unique ID"""

    class_name: str
    persistent_id: int
    confidence: float
    age_ms: int
    center: Point2D
    bbox: BoundingBox
    primary_track: bool = False
