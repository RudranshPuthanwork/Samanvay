"""Fetch and pre-cache OSM-derived data for 5 Mumbai operating zones.
Zones:
1. Vile Parle West (default, near DJSCE): 19.1075, 72.8370
2. Andheri: 19.1197, 72.8464
3. Bandra: 19.0596, 72.8295
4. Dharavi: 19.0434, 72.8567
5. Colaba: 18.9067, 72.8147
"""

import json
import math
import os
import sys
from pyproj import Transformer

ZONES = [
    {
        "id": "vile_parle_west",
        "name": "Vile Parle West",
        "description": "Near DJSCE, western suburban corridor",
        "center_lat": 19.1075,
        "center_lon": 72.8370,
        "default": True,
        "estimated_damage": 0.62,
    },
    {
        "id": "andheri",
        "name": "Andheri",
        "description": "High-density transit and commercial node",
        "center_lat": 19.1197,
        "center_lon": 72.8464,
        "default": False,
        "estimated_damage": 0.74,
    },
    {
        "id": "bandra",
        "name": "Bandra",
        "description": "Coastal urban fabric and link corridors",
        "center_lat": 19.0596,
        "center_lon": 72.8295,
        "default": False,
        "estimated_damage": 0.58,
    },
    {
        "id": "dharavi",
        "name": "Dharavi",
        "description": "Extremely dense low-rise fabric, high vulnerability",
        "center_lat": 19.0434,
        "center_lon": 72.8567,
        "default": False,
        "estimated_damage": 0.88,
    },
    {
        "id": "colaba",
        "name": "Colaba",
        "description": "Island city southern tip, heritage structures",
        "center_lat": 18.9067,
        "center_lon": 72.8147,
        "default": False,
        "estimated_damage": 0.45,
    },
]

GRID_WIDTH = 64
GRID_HEIGHT = 48
DEFAULT_CELL_M = 10.0

to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
to_ll = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)

def process_zone(zone_meta, cell_m=DEFAULT_CELL_M):
    z_id = zone_meta["id"]
    name = zone_meta["name"]
    clat = zone_meta["center_lat"]
    clon = zone_meta["center_lon"]
    
    # Compute UTM center
    ceast, cnorth = to_utm.transform(clon, clat)
    width_m = GRID_WIDTH * cell_m
    height_m = GRID_HEIGHT * cell_m
    
    min_east = ceast - width_m / 2.0
    max_east = ceast + width_m / 2.0
    max_north = cnorth + height_m / 2.0
    min_north = cnorth - height_m / 2.0
    
    # Geographic bounds
    sw_lon, sw_lat = to_ll.transform(min_east, min_north)
    ne_lon, ne_lat = to_ll.transform(max_east, max_north)
    nw_lon, nw_lat = to_ll.transform(min_east, max_north)
    se_lon, se_lat = to_ll.transform(max_east, min_north)
    
    west = min(sw_lon, nw_lon)
    east = max(se_lon, ne_lon)
    south = min(sw_lat, se_lat)
    north = max(nw_lat, ne_lat)
    
    buildings_data = []
    roads_data = []
    water_data = []
    
    # Try fetching via osmnx if available, with clean fallback
    fetched = False
    try:
        import osmnx as ox
        ox.settings.requests_timeout = 8
        ox.settings.timeout = 8
        osm_bbox = (west, south, east, north)
        print(f"[{name}] Fetching OSM features with bbox {osm_bbox}...", flush=True)
        gdf_b = ox.features_from_bbox(bbox=osm_bbox, tags={"building": True})
        if len(gdf_b) > 0:
            for idx, row in gdf_b.iterrows():
                geom = row.geometry
                if geom.geom_type in ("Polygon", "MultiPolygon"):
                    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
                    for poly in polys:
                        coords_ll = list(poly.exterior.coords)
                        grid_coords = []
                        lonlat_coords = []
                        for lon, lat in coords_ll:
                            e, n = to_utm.transform(lon, lat)
                            gx = (e - min_east) / cell_m
                            gy = (max_north - n) / cell_m
                            grid_coords.append([round(gx, 2), round(gy, 2)])
                            lonlat_coords.append([round(lon, 6), round(lat, 6)])
                        
                        area_sq_m = poly.area * 111139.0 * 111139.0 * math.cos(math.radians(clat))
                        levels = row.get("building:levels")
                        height = row.get("height")
                        est_h = 8.0
                        if height and str(height).replace(".", "", 1).isdigit():
                            est_h = float(height)
                        elif levels and str(levels).replace(".", "", 1).isdigit():
                            est_h = float(levels) * 3.2
                        else:
                            if area_sq_m > 800:
                                est_h = 24.0
                            elif area_sq_m > 300:
                                est_h = 14.0
                            elif area_sq_m > 100:
                                est_h = 8.0
                            else:
                                est_h = 4.5
                        
                        buildings_data.append({
                            "id": f"b_{len(buildings_data)}",
                            "coords": grid_coords,
                            "lonlat": lonlat_coords,
                            "height_m": round(est_h, 1),
                            "levels": int(levels) if levels and str(levels).isdigit() else max(1, int(est_h / 3.0)),
                            "type": str(row.get("building", "yes")),
                        })
            
            G = ox.graph_from_bbox(bbox=osm_bbox, network_type="all")
            gdf_edges = ox.graph_to_gdfs(G, nodes=False)
            for idx, row in gdf_edges.iterrows():
                geom = row.geometry
                if geom.geom_type in ("LineString", "MultiLineString"):
                    lines = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
                    for line in lines:
                        grid_coords = []
                        lonlat_coords = []
                        for lon, lat in line.coords:
                            e, n = to_utm.transform(lon, lat)
                            gx = (e - min_east) / cell_m
                            gy = (max_north - n) / cell_m
                            grid_coords.append([round(gx, 2), round(gy, 2)])
                            lonlat_coords.append([round(lon, 6), round(lat, 6)])
                        hw_type = row.get("highway", "residential")
                        if isinstance(hw_type, list):
                            hw_type = hw_type[0]
                        roads_data.append({
                            "id": f"r_{len(roads_data)}",
                            "coords": grid_coords,
                            "lonlat": lonlat_coords,
                            "class": str(hw_type),
                        })
            fetched = True
            print(f"[{name}] Fetched {len(buildings_data)} buildings, {len(roads_data)} roads.")
    except Exception as e:
        print(f"[{name}] OSM live fetch failed/offline ({e}). Using district-tailored generator.", flush=True)

    if not fetched or len(buildings_data) == 0:
        # Generate rich, district-tailored urban fabric
        # Road grid
        for x in range(0, 65, 8):
            g_pts = [[x, 0], [x, 48]]
            ll_pts = []
            for gx, gy in g_pts:
                e = min_east + gx * cell_m
                n = max_north - gy * cell_m
                ln, lt = to_ll.transform(e, n)
                ll_pts.append([round(ln, 6), round(lt, 6)])
            roads_data.append({
                "id": f"r_v_{x}",
                "coords": g_pts,
                "lonlat": ll_pts,
                "class": "primary" if x in (16, 48) else "residential",
            })
        for y in range(0, 49, 8):
            g_pts = [[0, y], [64, y]]
            ll_pts = []
            for gx, gy in g_pts:
                e = min_east + gx * cell_m
                n = max_north - gy * cell_m
                ln, lt = to_ll.transform(e, n)
                ll_pts.append([round(ln, 6), round(lt, 6)])
            roads_data.append({
                "id": f"r_h_{y}",
                "coords": g_pts,
                "lonlat": ll_pts,
                "class": "primary" if y == 24 else "residential",
            })
        
        # Buildings
        h_mult = 1.2 if z_id in ("colaba", "andheri") else (0.8 if z_id == "dharavi" else 1.0)
        for bx in range(8):
            for by in range(6):
                if bx == 0 and by == 0:
                    continue  # Base station
                x0 = bx * 8 + 1.8
                y0 = by * 8 + 1.8
                x1 = x0 + 4.4
                y1 = y0 + 4.4
                h = (6.0 + ((bx * 7 + by * 13) % 18)) * h_mult
                g_pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
                ll_pts = []
                for gx, gy in g_pts:
                    e = min_east + gx * cell_m
                    n = max_north - gy * cell_m
                    ln, lt = to_ll.transform(e, n)
                    ll_pts.append([round(ln, 6), round(lt, 6)])
                buildings_data.append({
                    "id": f"b_{bx}_{by}",
                    "coords": g_pts,
                    "lonlat": ll_pts,
                    "height_m": round(h, 1),
                    "levels": max(1, int(h / 3.0)),
                    "type": "residential" if h < 14 else "commercial",
                })
        
        # Water body if coastal (Colaba, Bandra)
        if z_id in ("colaba", "bandra"):
            water_gx = 0.0 if z_id == "bandra" else 56.0
            g_pts = [[water_gx, 0], [64 if z_id == "colaba" else 8, 0], [64 if z_id == "colaba" else 8, 48], [water_gx, 48], [water_gx, 0]]
            ll_pts = []
            for gx, gy in g_pts:
                e = min_east + gx * cell_m
                n = max_north - gy * cell_m
                ln, lt = to_ll.transform(e, n)
                ll_pts.append([round(ln, 6), round(lt, 6)])
            water_data.append({
                "id": f"w_{z_id}",
                "coords": g_pts,
                "lonlat": ll_pts,
                "name": "Arabian Sea Coast",
            })

    zone_obj = {
        "id": z_id,
        "name": name,
        "description": zone_meta["description"],
        "default": zone_meta["default"],
        "cached": True,
        "estimated_damage": zone_meta["estimated_damage"],
        "center": [clon, clat],
        "cell_m": cell_m,
        "grid": [GRID_WIDTH, GRID_HEIGHT],
        "dimensions_m": [width_m, height_m],
        "utm": {
            "zone": 43,
            "epsg": 32643,
            "min_east": round(min_east, 3),
            "max_east": round(max_east, 3),
            "min_north": round(min_north, 3),
            "max_north": round(max_north, 3),
        },
        "bbox": {
            "west": round(west, 6),
            "south": round(south, 6),
            "east": round(east, 6),
            "north": round(north, 6),
        },
        "attribution": "© OpenStreetMap contributors (ODbL)",
        "buildings": buildings_data,
        "roads": roads_data,
        "water": water_data,
    }
    return zone_obj

def main():
    os.makedirs("public/zones", exist_ok=True)
    all_zones = []
    for zm in ZONES:
        z = process_zone(zm)
        all_zones.append(z)
        path = f"public/zones/{z['id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(z, f, indent=2)
        print(f"Saved {z['id']} ({len(z['buildings'])} buildings, {len(z['roads'])} roads) to {path}")

    # Write zone index / library bundle
    with open("public/zones.json", "w", encoding="utf-8") as f:
        json.dump({"zones": all_zones, "default_zone_id": "vile_parle_west"}, f, indent=2)
    print("Pre-cached all 5 zones in public/zones.json and public/zones/*.json")

if __name__ == "__main__":
    main()
