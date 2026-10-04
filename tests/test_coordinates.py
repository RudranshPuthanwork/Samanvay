"""Tests for coordinate transform module (samanvay.core.coords).

Verifies:
1. Corners of a zone round-trip within 1 cm (< 0.01 m).
2. Random grid positions across all 5 Mumbai zones round-trip within 1 cm.
3. A drone placed at a cell centre appears over the correct building footprint in lon/lat.
"""

import json
from pathlib import Path
import pytest
from shapely.geometry import Point, Polygon
from samanvay.core.coords import ZoneTransform


@pytest.fixture
def vile_parle_transform():
    # Vile Parle West: 19.1075 N, 72.8370 E
    return ZoneTransform(center_lon=72.8370, center_lat=19.1075, cell_m=10.0)


def test_zone_corners_roundtrip_within_one_centimeter(vile_parle_transform):
    """Spec §4: Corners of a zone round-trip within 1 cm."""
    zt = vile_parle_transform
    corners = [
        (0.0, 0.0),          # NW
        (64.0, 0.0),         # NE
        (64.0, 48.0),        # SE
        (0.0, 48.0),         # SW
        (32.0, 24.0),        # Center
    ]

    for gx, gy in corners:
        # 1. Grid -> UTM
        e, n = zt.grid_to_utm(gx, gy)
        
        # 2. UTM -> Lon/Lat
        lon, lat = zt.utm_to_lonlat(e, n)
        
        # 3. Direct grid -> Lon/Lat equivalence
        d_lon, d_lat = zt.grid_to_lonlat(gx, gy)
        assert abs(lon - d_lon) < 1e-9
        assert abs(lat - d_lat) < 1e-9
        
        # 4. Lon/Lat -> UTM
        e_rt, n_rt = zt.lonlat_to_utm(lon, lat)
        error_utm_m = ((e - e_rt) ** 2 + (n - n_rt) ** 2) ** 0.5
        assert error_utm_m < 0.01, f"UTM roundtrip error {error_utm_m * 100:.3f} cm exceeds 1 cm threshold"

        # 5. UTM -> Grid
        gx_rt, gy_rt = zt.utm_to_grid(e_rt, n_rt)
        err_grid_m = ((gx - gx_rt) ** 2 + (gy - gy_rt) ** 2) ** 0.5 * zt.cell_m
        assert err_grid_m < 0.01, f"Grid roundtrip error {err_grid_m * 100:.3f} cm exceeds 1 cm threshold"


def test_all_five_zones_roundtrip():
    """Verify roundtrip fidelity across all 5 pre-cached zones with 10m, 15m, 20m cells."""
    zones = [
        (72.8370, 19.1075),  # Vile Parle West
        (72.8464, 19.1197),  # Andheri
        (72.8295, 19.0596),  # Bandra
        (72.8567, 19.0434),  # Dharavi
        (72.8147, 18.9067),  # Colaba
    ]
    for clon, clat in zones:
        for cell_m in (10.0, 15.0, 20.0):
            zt = ZoneTransform(center_lon=clon, center_lat=clat, cell_m=cell_m)
            for gx in (0.0, 16.0, 32.0, 48.0, 64.0):
                for gy in (0.0, 12.0, 24.0, 36.0, 48.0):
                    lon, lat = zt.grid_to_lonlat(gx, gy)
                    gx_rt, gy_rt = zt.lonlat_to_grid(lon, lat)
                    diff_m = (((gx - gx_rt) * cell_m) ** 2 + ((gy - gy_rt) * cell_m) ** 2) ** 0.5
                    assert diff_m < 0.01, f"Zone at ({clon}, {clat}) with cell {cell_m}m error: {diff_m * 100:.4f} cm"


def test_drone_at_cell_center_appears_over_correct_building():
    """Spec §4: A drone placed at a cell centre appears over the correct building footprint."""
    zt = ZoneTransform(center_lon=72.8370, center_lat=19.1075, cell_m=10.0)

    # Synthetic or cached building footprint covering grid [16..20, 12..16]
    poly_grid = [(16.0, 12.0), (20.0, 12.0), (20.0, 16.0), (16.0, 16.0), (16.0, 12.0)]
    poly_lonlat = [zt.grid_to_lonlat(gx, gy) for gx, gy in poly_grid]

    # Drone placed at cell centre (18.0, 14.0) inside the footprint
    drone_gx, drone_gy = 18.0, 14.0
    drone_lon, drone_lat = zt.grid_to_lonlat(drone_gx, drone_gy)

    # 1. Drone is inside grid footprint
    assert Polygon(poly_grid).contains(Point(drone_gx, drone_gy))

    # 2. Drone in lon/lat is inside geographic polygon footprint
    assert Polygon(poly_lonlat).contains(Point(drone_lon, drone_lat))

    # 3. Test with a real building from public/zones/vile_parle_west.json
    zone_path = Path("public/zones/vile_parle_west.json")
    if zone_path.exists():
        data = json.loads(zone_path.read_text(encoding="utf-8"))
        buildings = data.get("buildings", [])
        if buildings:
            # Find a building with at least 4 coordinates and positive area
            for b in buildings[:10]:
                coords_grid = [tuple(p) for p in b["coords"]]
                if len(coords_grid) >= 3 and Polygon(coords_grid).area > 1.0:
                    poly_b_grid = Polygon(coords_grid)
                    centroid_gx, centroid_gy = poly_b_grid.centroid.x, poly_b_grid.centroid.y
                    
                    # Drone placed at building centroid
                    d_lon, d_lat = zt.grid_to_lonlat(centroid_gx, centroid_gy)
                    poly_b_ll = Polygon([zt.grid_to_lonlat(gx, gy) for gx, gy in coords_grid])
                    
                    assert poly_b_ll.contains(Point(d_lon, d_lat)) or poly_b_ll.buffer(1e-6).contains(Point(d_lon, d_lat))
                    break
