/**
 * Simulated City-Scale Earthquake Intensity Model (Spec §6.1.3 & Phase 3 §1.1).
 *
 * Intensity formula:
 * I(x, y) = I0 * exp(-d / d0)
 *
 * Parameters:
 * - I0: 8.5 MMI (Modified Mercalli Intensity at epicentre) [ASSUMPTION]
 * - d0: 7500.0 m (7.5 km city-scale decay length) [ASSUMPTION]
 *
 * Renders on screen with label "simulated".
 * Allows interactive epicentre placement via map click or drag.
 */

export interface Epicentre {
  lon: number;
  lat: number;
  depth_km: number;
  magnitude: number;
  intensity_i0: number; // MMI scale (e.g. 8.5)
  decay_d0_m: number; // 7500m
}

export const DEFAULT_EPICENTRE: Epicentre = {
  lon: 72.805, // Offshore fault line near Arabian Sea west of Bandra/Worli
  lat: 19.045,
  depth_km: 12.0,
  magnitude: 6.7,
  intensity_i0: 8.5,
  decay_d0_m: 7500.0,
};

// Haversine distance in meters
export function haversineDistanceM(
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number
): number {
  const R = 6371000.0; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180.0;
  const dLon = ((lon2 - lon1) * Math.PI) / 180.0;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180.0) *
      Math.cos((lat2 * Math.PI) / 180.0) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Compute earthquake intensity at (lon, lat) given an epicentre.
 * Returns MMI intensity [1.0 .. I0].
 */
export function computeIntensity(
  lon: number,
  lat: number,
  epicentre: Epicentre = DEFAULT_EPICENTRE
): number {
  const d_m = haversineDistanceM(epicentre.lon, epicentre.lat, lon, lat);
  const hypo_d_m = Math.sqrt(d_m * d_m + Math.pow(epicentre.depth_km * 1000.0, 2));
  return epicentre.intensity_i0 * Math.exp(-hypo_d_m / epicentre.decay_d0_m);
}

export interface DistrictExposure {
  id: string;
  name: string;
  center: [number, number];
  distance_km: number;
  intensity_mmi: number;
  vulnerability: number; // [0.1 .. 1.0]
  damage_exposure: number; // [0.0 .. 1.0]
  cached: boolean;
}

export const DISTRICT_VULNERABILITY: Record<string, number> = {
  vile_parle_west: 0.65,
  andheri: 0.75,
  bandra: 0.60,
  dharavi: 0.95, // extremely dense informal fabric
  colaba: 0.70, // heritage unreinforced masonry
  dadar: 0.68,
  kurla: 0.78,
  worli: 0.55,
  chembur: 0.62,
  malad: 0.58,
  borivali: 0.52,
};

/**
 * Rank Mumbai zones and districts by estimated damage exposure.
 */
export function rankDistrictsByExposure(
  epicentre: Epicentre,
  zones: Array<{ id: string; name: string; center: [number, number]; cached: boolean }>
): DistrictExposure[] {
  const results: DistrictExposure[] = zones.map((z) => {
    const d_m = haversineDistanceM(epicentre.lon, epicentre.lat, z.center[0], z.center[1]);
    const intensity = computeIntensity(z.center[0], z.center[1], epicentre);
    const vuln = DISTRICT_VULNERABILITY[z.id] || 0.65;
    const rawExposure = (intensity / epicentre.intensity_i0) * vuln;
    const exposure = Math.min(1.0, Math.max(0.05, Math.round(rawExposure * 100) / 100));

    return {
      id: z.id,
      name: z.name,
      center: z.center,
      distance_km: Math.round((d_m / 1000.0) * 10) / 10,
      intensity_mmi: Math.round(intensity * 10) / 10,
      vulnerability: vuln,
      damage_exposure: exposure,
      cached: z.cached,
    };
  });

  return results.sort((a, b) => b.damage_exposure - a.damage_exposure);
}

/**
 * Generate concentric intensity contour rings around epicentre for deck.gl LineLayer / PathLayer.
 */
export function generateIntensityRings(
  epicentre: Epicentre,
  levels: number[] = [4.0, 5.0, 6.0, 7.0, 8.0]
): Array<{ level: number; coordinates: [number, number][] }> {
  const rings: Array<{ level: number; coordinates: [number, number][] }> = [];

  for (const mmi of levels) {
    if (mmi >= epicentre.intensity_i0) continue;
    // Solve I = I0 * exp(-hypo_d / d0) => hypo_d = -d0 * ln(I / I0)
    const hypo_d = -epicentre.decay_d0_m * Math.log(mmi / epicentre.intensity_i0);
    const depth_m = epicentre.depth_km * 1000.0;
    if (hypo_d <= depth_m) continue;
    const radius_m = Math.sqrt(hypo_d * hypo_d - depth_m * depth_m);

    // Generate circle coordinates
    const coords: [number, number][] = [];
    const nPts = 64;
    const latRad = (epicentre.lat * Math.PI) / 180.0;
    const m_per_deg_lat = 111139.0;
    const m_per_deg_lon = 111139.0 * Math.cos(latRad);

    for (let i = 0; i <= nPts; i++) {
      const theta = (i / nPts) * 2 * Math.PI;
      const dx = radius_m * Math.cos(theta);
      const dy = radius_m * Math.sin(theta);
      const lon = epicentre.lon + dx / m_per_deg_lon;
      const lat = epicentre.lat + dy / m_per_deg_lat;
      coords.push([lon, lat]);
    }

    rings.push({ level: mmi, coordinates: coords });
  }

  return rings;
}
