/**
 * Custom MapLibre Style from DESIGN.md tokens (Spec §3.3).
 *
 * Rules:
 * - NO stock themes.
 * - Flat muted tones: ground (#101215), landuse (#1B2025), water (#2E4A5A), roads (#3A424A).
 * - Buildings: fill-extrusion from zoom 15 with flat muted color (#2C3238).
 * - ZERO text layers and ZERO icon layers in the MapLibre style (no glyph/sprite network requests).
 * - Orientation labels are rendered via deck.gl TextLayer in IBM Plex Sans 12px using cached coordinates.
 */

import type { StyleSpecification } from "maplibre-gl";

export interface PlaceLabel {
  name: string;
  coordinates: [number, number]; // [lon, lat]
  importance: "primary" | "secondary";
  zoneId?: string;
}

export const MUMBAI_ORIENTATION_PLACES: PlaceLabel[] = [
  { name: "Vile Parle West", coordinates: [72.8370, 19.1075], importance: "primary", zoneId: "vile_parle_west" },
  { name: "Andheri", coordinates: [72.8464, 19.1197], importance: "primary", zoneId: "andheri" },
  { name: "Bandra", coordinates: [72.8295, 19.0596], importance: "primary", zoneId: "bandra" },
  { name: "Dharavi", coordinates: [72.8567, 19.0434], importance: "primary", zoneId: "dharavi" },
  { name: "Colaba", coordinates: [72.8147, 18.9067], importance: "primary", zoneId: "colaba" },
  { name: "Dadar", coordinates: [72.8437, 19.0178], importance: "secondary" },
  { name: "Kurla", coordinates: [72.8797, 19.0657], importance: "secondary" },
  { name: "Worli", coordinates: [72.8181, 19.0134], importance: "secondary" },
  { name: "Chembur", coordinates: [72.8997, 19.0622], importance: "secondary" },
  { name: "Juhu", coordinates: [72.8260, 19.0988], importance: "secondary" },
  { name: "Santacruz", coordinates: [72.8400, 19.0800], importance: "secondary" },
  { name: "Malad", coordinates: [72.8485, 19.1860], importance: "secondary" },
  { name: "Borivali", coordinates: [72.8566, 19.2288], importance: "secondary" },
  { name: "Fort / CSMT", coordinates: [72.8347, 18.9398], importance: "secondary" },
  { name: "Marine Drive", coordinates: [72.8236, 18.9438], importance: "secondary" },
];

export function createMumbaiMapStyle(pmtilesUrl = "/mumbai.pmtiles"): StyleSpecification {
  const origin = typeof window !== "undefined" && window.location.origin
    ? window.location.origin
    : "http://127.0.0.1:8000";

  const absoluteTilesUrl = pmtilesUrl.startsWith("http")
    ? pmtilesUrl
    : `${origin}${pmtilesUrl.startsWith("/") ? "" : "/"}${pmtilesUrl}`;

  return {
    version: 8,
    name: "SAMANVAY Mumbai Offline Basemap",
    sources: {
      protomaps_mumbai: {
        type: "vector",
        url: `pmtiles://${absoluteTilesUrl}`,
        attribution: "© OpenStreetMap contributors (ODbL) · Protomaps",
      },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: {
          "background-color": "#101215", // ground
        },
      },
      {
        id: "earth",
        type: "fill",
        source: "protomaps_mumbai",
        "source-layer": "earth",
        paint: {
          "fill-color": "#101215",
        },
      },
      {
        id: "landuse",
        type: "fill",
        source: "protomaps_mumbai",
        "source-layer": "landuse",
        paint: {
          "fill-color": "#1B2025", // open ground one-step tonal shift
          "fill-opacity": 0.8,
        },
      },
      {
        id: "water",
        type: "fill",
        source: "protomaps_mumbai",
        "source-layer": "water",
        paint: {
          "fill-color": "#2E4A5A", // water token from DESIGN.md
        },
      },
      {
        id: "roads_minor",
        type: "line",
        source: "protomaps_mumbai",
        "source-layer": "roads",
        minzoom: 11,
        paint: {
          "line-color": "#323A42",
          "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.5, 14, 1.0, 16, 1.5],
        },
      },
      {
        id: "roads_major",
        type: "line",
        source: "protomaps_mumbai",
        "source-layer": "roads",
        paint: {
          "line-color": "#3A424A", // road token
          "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.75, 13, 1.5, 16, 2.5],
        },
      },
      {
        id: "buildings_extrusion",
        type: "fill-extrusion",
        source: "protomaps_mumbai",
        "source-layer": "buildings",
        minzoom: 15,
        paint: {
          "fill-extrusion-color": "#2C3238", // building token
          "fill-extrusion-height": [
            "interpolate",
            ["linear"],
            ["zoom"],
            15,
            ["*", ["coalesce", ["get", "height"], 10], 0.5],
            17,
            ["coalesce", ["get", "height"], 12],
          ],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.85,
        },
      },
    ],
  };
}
