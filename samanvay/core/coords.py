"""Single tested coordinate transform module for SAMANVAY.

Handles conversions between:
1. Simulation grid cells (gx, gy) ∈ [0..64, 0..48]
2. Metric UTM Zone 43N coordinates (Easting, Northing in meters, EPSG:32643)
3. Geographic coordinates (Longitude, Latitude in degrees, WGS84, EPSG:4326)

All transforms maintain millimeter-level roundtrip fidelity (< 0.001 m).
"""

from dataclasses import dataclass
from typing import Tuple
from pyproj import Transformer
from shapely.geometry import Point, Polygon

EPSG_WGS84 = "EPSG:4326"
EPSG_UTM43N = "EPSG:32643"

_to_utm = Transformer.from_crs(EPSG_WGS84, EPSG_UTM43N, always_xy=True)
_to_ll = Transformer.from_crs(EPSG_UTM43N, EPSG_WGS84, always_xy=True)


@dataclass(frozen=True)
class ZoneTransform:
    """Rigorous metric projection for a 64x48 simulation zone."""
    center_lon: float
    center_lat: float
    cell_m: float = 10.0
    grid_w: int = 64
    grid_h: int = 48

    @property
    def center_utm(self) -> Tuple[float, float]:
        east, north = _to_utm.transform(self.center_lon, self.center_lat)
        return (east, north)

    @property
    def min_east(self) -> float:
        ce, _ = self.center_utm
        return ce - (self.grid_w * self.cell_m) / 2.0

    @property
    def max_east(self) -> float:
        ce, _ = self.center_utm
        return ce + (self.grid_w * self.cell_m) / 2.0

    @property
    def max_north(self) -> float:
        _, cn = self.center_utm
        return cn + (self.grid_h * self.cell_m) / 2.0

    @property
    def min_north(self) -> float:
        _, cn = self.center_utm
        return cn - (self.grid_h * self.cell_m) / 2.0

    def grid_to_utm(self, gx: float, gy: float) -> Tuple[float, float]:
        """Convert simulation grid coordinate to UTM Zone 43N (meters).
        gx: 0 is West, grid_w is East.
        gy: 0 is North, grid_h is South.
        """
        easting = self.min_east + gx * self.cell_m
        northing = self.max_north - gy * self.cell_m
        return (easting, northing)

    def utm_to_grid(self, easting: float, northing: float) -> Tuple[float, float]:
        """Convert UTM Zone 43N coordinates (meters) to simulation grid."""
        gx = (easting - self.min_east) / self.cell_m
        gy = (self.max_north - northing) / self.cell_m
        return (gx, gy)

    def utm_to_lonlat(self, easting: float, northing: float) -> Tuple[float, float]:
        """Convert UTM Zone 43N to WGS84 (lon, lat)."""
        lon, lat = _to_ll.transform(easting, northing)
        return (lon, lat)

    def lonlat_to_utm(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 (lon, lat) to UTM Zone 43N."""
        east, north = _to_utm.transform(lon, lat)
        return (east, north)

    def grid_to_lonlat(self, gx: float, gy: float) -> Tuple[float, float]:
        """Direct conversion: grid cell (gx, gy) -> WGS84 (lon, lat)."""
        e, n = self.grid_to_utm(gx, gy)
        return self.utm_to_lonlat(e, n)

    def lonlat_to_grid(self, lon: float, lat: float) -> Tuple[float, float]:
        """Direct conversion: WGS84 (lon, lat) -> grid cell (gx, gy)."""
        e, n = self.lonlat_to_utm(lon, lat)
        return self.utm_to_grid(e, n)

    def get_bbox_lonlat(self) -> dict[str, float]:
        """Return geographic bounding box for the zone."""
        sw_lon, sw_lat = self.utm_to_lonlat(self.min_east, self.min_north)
        ne_lon, ne_lat = self.utm_to_lonlat(self.max_east, self.max_north)
        nw_lon, nw_lat = self.utm_to_lonlat(self.min_east, self.max_north)
        se_lon, se_lat = self.utm_to_lonlat(self.max_east, self.min_north)
        return {
            "west": min(sw_lon, nw_lon),
            "south": min(sw_lat, se_lat),
            "east": max(se_lon, ne_lon),
            "north": max(nw_lat, ne_lat),
        }

    def contains_point_grid(self, building_poly_grid: list[Tuple[float, float]], drone_gx: float, drone_gy: float) -> bool:
        """Check if drone at (drone_gx, drone_gy) is inside a building footprint in grid coords."""
        poly = Polygon(building_poly_grid)
        return poly.contains(Point(drone_gx, drone_gy))

    def contains_point_lonlat(self, building_poly_lonlat: list[Tuple[float, float]], drone_lon: float, drone_lat: float) -> bool:
        """Check if drone at (drone_lon, drone_lat) is inside a building footprint in geographic coords."""
        poly = Polygon(building_poly_lonlat)
        return poly.contains(Point(drone_lon, drone_lat))
