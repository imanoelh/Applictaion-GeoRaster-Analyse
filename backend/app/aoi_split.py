from __future__ import annotations

import math
from typing import Any

from .scalability import MAX_LOGICAL_CHUNKS


KM_PER_DEG_LAT = 110.57
# Number of cells laid along the longest side of the AOI when the caller does
# not choose a part count. The other side gets as many cells as needed to
# keep the cells roughly square.
CELLS_ALONG_LENGTH = 4

# A piece is a list of polygons; a polygon is a list of closed rings
# [outer, hole, ...]; a ring is a list of [lon, lat] points.
Ring = list[list[float]]
Polygon = list[Ring]
Piece = list[Polygon]


class AoiSplitError(ValueError):
    """Raised when an AOI cannot be split into parts."""


def _km_per_deg_lon(latitude: float) -> float:
    return 111.32 * max(math.cos(math.radians(latitude)), 0.25)


def _polygons_from_geometry(geometry: dict[str, Any]) -> Piece:
    geometry_type = str((geometry or {}).get("type") or "")
    coordinates = (geometry or {}).get("coordinates") or []
    if geometry_type == "Polygon":
        return [[_closed_ring(ring) for ring in coordinates if ring]]
    if geometry_type == "MultiPolygon":
        return [[_closed_ring(ring) for ring in polygon if ring] for polygon in coordinates if polygon]
    raise AoiSplitError("Geometry must be a Polygon or a MultiPolygon.")


def _closed_ring(ring: Any) -> Ring:
    points = [[float(point[0]), float(point[1])] for point in ring]
    if len(points) >= 2 and points[0] != points[-1]:
        points.append(list(points[0]))
    return points


def _piece_bbox(piece: Piece) -> tuple[float, float, float, float]:
    """Return (south, west, north, east)."""
    longitudes: list[float] = []
    latitudes: list[float] = []
    for polygon in piece:
        for point in polygon[0]:
            longitudes.append(point[0])
            latitudes.append(point[1])
    if not longitudes:
        raise AoiSplitError("Geometry does not contain any coordinate.")
    return min(latitudes), min(longitudes), max(latitudes), max(longitudes)


def _ring_area_km2(ring: Ring, km_per_deg_lon: float) -> float:
    if len(ring) < 4:
        return 0.0
    doubled = 0.0
    for index in range(len(ring) - 1):
        x1 = ring[index][0] * km_per_deg_lon
        y1 = ring[index][1] * KM_PER_DEG_LAT
        x2 = ring[index + 1][0] * km_per_deg_lon
        y2 = ring[index + 1][1] * KM_PER_DEG_LAT
        doubled += (x1 * y2) - (x2 * y1)
    return abs(doubled) / 2.0


def _piece_area_km2(piece: Piece, km_per_deg_lon: float) -> float:
    total = 0.0
    for polygon in piece:
        outer = _ring_area_km2(polygon[0], km_per_deg_lon)
        holes = sum(_ring_area_km2(ring, km_per_deg_lon) for ring in polygon[1:])
        total += max(0.0, outer - holes)
    return total


def _clip_ring(ring: Ring, axis: int, value: float, keep_lower: bool) -> Ring | None:
    """Sutherland-Hodgman clip of one ring by a half-plane."""
    points = ring[:-1]
    if len(points) < 3:
        return None

    def inside(point: list[float]) -> bool:
        return point[axis] <= value if keep_lower else point[axis] >= value

    clipped: Ring = []
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        current_inside = inside(current)
        following_inside = inside(following)
        if current_inside:
            clipped.append(list(current))
        if current_inside != following_inside:
            span = following[axis] - current[axis]
            if span == 0:
                continue
            ratio = (value - current[axis]) / span
            crossing = [
                current[0] + ratio * (following[0] - current[0]),
                current[1] + ratio * (following[1] - current[1]),
            ]
            crossing[axis] = value
            clipped.append(crossing)
    if len(clipped) < 3:
        return None
    return clipped + [list(clipped[0])]


def _clip_piece(piece: Piece, axis: int, value: float, keep_lower: bool) -> Piece:
    clipped_piece: Piece = []
    for polygon in piece:
        outer = _clip_ring(polygon[0], axis, value, keep_lower)
        if outer is None:
            continue
        rings: Polygon = [outer]
        for hole in polygon[1:]:
            clipped_hole = _clip_ring(hole, axis, value, keep_lower)
            if clipped_hole is not None:
                rings.append(clipped_hole)
        clipped_piece.append(rings)
    return clipped_piece


def recommend_grid(
    width_km: float,
    height_km: float,
    cells_along_length: int = CELLS_ALONG_LENGTH,
) -> tuple[int, int]:
    """Rows and columns of the automatic grid, as (rows, columns).

    The longest side of the AOI carries `cells_along_length` cells; the other
    side carries as many as needed for the cells to stay roughly square.
    """
    try:
        along = int(cells_along_length)
    except (TypeError, ValueError):
        raise AoiSplitError("cells_along_length must be an integer.") from None
    if along < 1:
        raise AoiSplitError("cells_along_length must be greater than or equal to 1.")

    width = max(float(width_km), 1e-9)
    height = max(float(height_km), 1e-9)
    if width >= height:
        columns = along
        rows = max(1, round(along * height / width))
    else:
        rows = along
        columns = max(1, round(along * width / height))
    while rows * columns > MAX_LOGICAL_CHUNKS:
        if rows >= columns and rows > 1:
            rows -= 1
        elif columns > 1:
            columns -= 1
        else:  # pragma: no cover - unreachable while MAX_LOGICAL_CHUNKS >= 1
            break
    return rows, columns


def _grid_for_part_count(count: int, width_km: float, height_km: float) -> tuple[int, int]:
    """Rows and columns whose product is count, with the squarest cells."""
    best = (1, count)
    best_score = float("inf")
    for rows in range(1, count + 1):
        if count % rows:
            continue
        columns = count // rows
        cell_width = max(width_km / columns, 1e-9)
        cell_height = max(height_km / rows, 1e-9)
        score = abs(math.log(cell_width / cell_height))
        if score < best_score - 1e-12:
            best_score = score
            best = (rows, columns)
    return best


def _piece_to_geojson(piece: Piece) -> dict[str, Any]:
    if len(piece) == 1:
        return {"type": "Polygon", "coordinates": piece[0]}
    return {"type": "MultiPolygon", "coordinates": piece}


def geojson_area_km2(geometry: dict[str, Any]) -> float:
    """Area of a Polygon/MultiPolygon in km2, holes excluded."""
    piece = _polygons_from_geometry(geometry)
    south, _, north, _ = _piece_bbox(piece)
    return _piece_area_km2(piece, _km_per_deg_lon((south + north) / 2.0))


def split_aoi_grid(
    geometry: dict[str, Any],
    parts: int | str | None = None,
    cells_along_length: int = CELLS_ALONG_LENGTH,
) -> list[dict[str, Any]]:
    """Split an AOI along a regular grid drawn on its bounding box.

    The cut lines run across the whole AOI, so the cells are aligned rectangles
    - the ones on the border are trimmed by the AOI outline and therefore
    smaller. `parts` may be omitted or set to "auto": the grid then carries
    `cells_along_length` cells along the longest side of the AOI.

    Cells are returned in reading order - row 1 is the northern one, column 1
    the western one - and cells falling completely outside the AOI are dropped.
    """
    piece = _polygons_from_geometry(geometry)
    south, west, north, east = _piece_bbox(piece)
    km_per_deg_lon = _km_per_deg_lon((south + north) / 2.0)
    total_area = _piece_area_km2(piece, km_per_deg_lon)
    if total_area <= 0:
        raise AoiSplitError("The geometry has no surface to split.")

    width_km = (east - west) * km_per_deg_lon
    height_km = (north - south) * KM_PER_DEG_LAT

    if parts is None or (isinstance(parts, str) and parts.strip().lower() == "auto"):
        rows, columns = recommend_grid(width_km, height_km, cells_along_length)
    else:
        try:
            count = int(parts)
        except (TypeError, ValueError):
            raise AoiSplitError('The number of parts must be an integer or "auto".') from None
        if count < 1:
            raise AoiSplitError("The number of parts must be greater than or equal to 1.")
        rows, columns = _grid_for_part_count(count, width_km, height_km)

    latitude_step = (north - south) / rows
    longitude_step = (east - west) / columns

    items: list[dict[str, Any]] = []
    for row_index in range(rows):
        # Row 1 is the northern one.
        cell_north = north - row_index * latitude_step
        cell_south = cell_north - latitude_step
        band = _clip_piece(piece, 1, cell_north, True)
        band = _clip_piece(band, 1, cell_south, False)
        if not band:
            continue
        for column_index in range(columns):
            cell_west = west + column_index * longitude_step
            cell_east = cell_west + longitude_step
            cell = _clip_piece(band, 0, cell_east, True)
            cell = _clip_piece(cell, 0, cell_west, False)
            if not cell:
                continue
            area_km2 = _piece_area_km2(cell, km_per_deg_lon)
            if area_km2 <= 0:
                continue
            items.append({
                "part_id": f"part_{len(items) + 1:02d}",
                "row": row_index + 1,
                "column": column_index + 1,
                "geojson": _piece_to_geojson(cell),
                "bbox": list(_piece_bbox(cell)),
                "area_km2": round(area_km2, 6),
                "area_share": round(area_km2 / total_area, 6),
            })
    if not items:
        raise AoiSplitError("The geometry has no surface to split.")
    return items
