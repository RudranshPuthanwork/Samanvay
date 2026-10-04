import React, { useEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { MapView } from "@deck.gl/core";
import {
  PolygonLayer,
  PathLayer,
  ScatterplotLayer,
  LineLayer,
  ArcLayer,
} from "@deck.gl/layers";
import { contours } from "d3-contour";
import { AgentState, DetectionItem, Forecast } from "../types";
import defaultOsmData from "../data/osm_vile_parle.json";

export interface DeckMapRendererProps {
  gridSize: [number, number];
  terrain: string[][];
  plume: number[][];
  beliefHeatmap: number[][];
  agents: Record<string, AgentState>;
  detections: DetectionItem[];
  radioEdges: [string, string][];
  forecast?: Forecast | null | undefined;
  wind?: { deg: number; mps: number } | undefined;
  activeEscalation?: boolean | undefined;
  escalationTarget?: [number, number] | null | undefined;
  selectedAgentId?: string | null | undefined;
  onSelectAgent?: ((id: string | null) => void) | undefined;
  onToggle2D: () => void;
}

interface OsmDistrictData {
  district: string;
  attribution: string;
  bbox: {
    north: number;
    south: number;
    east: number;
    west: number;
    center: [number, number];
  };
  buildings: Array<{
    id: string;
    coords: [number, number][];
    height_m: number;
    levels: number;
    type: string;
  }>;
  roads: Array<{
    id: string;
    coords: [number, number][];
    class: string;
  }>;
}

export const DeckMapRenderer: React.FC<DeckMapRendererProps> = ({
  gridSize,
  terrain,
  plume,
  beliefHeatmap,
  agents,
  detections,
  radioEdges,
  forecast,
  wind = { deg: 225, mps: 4.5 },
  activeEscalation,
  escalationTarget,
  selectedAgentId,
  onSelectAgent,
  onToggle2D,
}) => {
  const [osmData, setOsmData] = useState<OsmDistrictData>(defaultOsmData as unknown as OsmDistrictData);
  const [isTopView, setIsTopView] = useState(false);
  const [animTime, setAnimTime] = useState(0);

  // Position history for 20s time-fade trails
  const historyRef = useRef<Record<string, Array<{ pos: [number, number]; t: number }>>>({});

  // Bounding box for Vile Parle district
  const bbox = osmData?.bbox || {
    north: 19.109659,
    south: 19.105341,
    east: 72.840047,
    west: 72.833953,
    center: [19.1075, 72.837] as [number, number],
  };

  // Convert grid coords [x: 0..64, y: 0..48] to Lon/Lat
  const gridToLonLat = (gx: number, gy: number): [number, number] => {
    const lon = bbox.west + (gx / gridSize[0]) * (bbox.east - bbox.west);
    const lat = bbox.north - (gy / gridSize[1]) * (bbox.north - bbox.south);
    return [lon, lat];
  };

  // Ensure fresh vector cache if served dynamically
  useEffect(() => {
    if (!osmData) {
      fetch("/osm_vile_parle.json")
        .then((r) => r.json())
        .then((d: OsmDistrictData) => setOsmData(d))
        .catch(() => {});
    }
  }, [osmData]);

  // Update agent trail history
  useEffect(() => {
    const now = Date.now() / 1000;
    const hist = historyRef.current;
    Object.entries(agents).forEach(([id, ag]) => {
      if (!hist[id]) hist[id] = [];
      const trail = hist[id];
      const last = trail[trail.length - 1];
      if (!last || last.pos[0] !== ag.pos[0] || last.pos[1] !== ag.pos[1]) {
        trail.push({ pos: ag.pos, t: now });
      }
      // Prune points older than 20 seconds
      historyRef.current[id] = trail.filter((p) => now - p.t <= 20);
    });
  }, [agents]);

  // Frame tick for wind flow particles and lease rings
  useEffect(() => {
    let animId: number;
    const step = () => {
      setAnimTime((t) => (t + 0.03) % 1000);
      animId = requestAnimationFrame(step);
    };
    animId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animId);
  }, []);

  // View state with smooth animation on escalation
  const [viewState, setViewState] = useState({
    longitude: 72.837,
    latitude: 19.1075,
    zoom: 16.7,
    pitch: 52,
    bearing: -18,
    transitionDuration: 0,
  });

  // Handle camera framing on escalation
  useEffect(() => {
    if (activeEscalation && escalationTarget) {
      const [exLon, exLat] = gridToLonLat(escalationTarget[0], escalationTarget[1]);
      setViewState((prev) => ({
        ...prev,
        longitude: exLon,
        latitude: exLat,
        zoom: 17.5,
        pitch: 45,
        transitionDuration: 600,
      }));
    } else if (!activeEscalation && escalationTarget) {
      // Return to district center
      setViewState((prev) => ({
        ...prev,
        longitude: 72.837,
        latitude: 19.1075,
        zoom: 16.7,
        pitch: isTopView ? 0 : 52,
        bearing: isTopView ? 0 : -18,
        transitionDuration: 600,
      }));
    }
  }, [activeEscalation, escalationTarget, isTopView]);

  const handleToggleTopView = () => {
    setIsTopView((v) => {
      const next = !v;
      setViewState((prev) => ({
        ...prev,
        pitch: next ? 0 : 52,
        bearing: next ? 0 : -18,
        transitionDuration: 400,
      }));
      return next;
    });
  };

  // 1. Terrain Ground Mesh & Base Pad
  const groundPolygon = [
    gridToLonLat(0, 0),
    gridToLonLat(gridSize[0], 0),
    gridToLonLat(gridSize[0], gridSize[1]),
    gridToLonLat(0, gridSize[1]),
    gridToLonLat(0, 0),
  ];

  const groundLayer = new PolygonLayer({
    id: "ground-plate",
    data: [{ polygon: groundPolygon }],
    getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
    getFillColor: [16, 18, 21], // #101215 ground
    getLineColor: [42, 48, 54], // #2A3036 rule
    getLineWidth: 1,
    lineWidthUnits: "pixels",
    stroked: true,
    filled: true,
  });

  // 2. Extruded 3D OSM Buildings (Survey Palette with Rubble Detection)
  const buildingsLayer = useMemo(() => {
    const bList = osmData?.buildings || [];
    return new PolygonLayer({
      id: "osm-buildings",
      data: bList,
      getPolygon: (b: any) => b.coords.map(([gx, gy]: [number, number]) => gridToLonLat(gx, gy)),
      extruded: true,
      getElevation: (b: any) => {
        // Check if building cell is collapsed to rubble in terrain
        const centerGx = Math.floor(b.coords[0]?.[0] ?? 0);
        const centerGy = Math.floor(b.coords[0]?.[1] ?? 0);
        const isRubble = terrain[centerGy]?.[centerGx] === "rubble";
        return isRubble ? 1.5 : Math.max(4.0, b.height_m);
      },
      getFillColor: (b: any) => {
        const centerGx = Math.floor(b.coords[0]?.[0] ?? 0);
        const centerGy = Math.floor(b.coords[0]?.[1] ?? 0);
        const isRubble = terrain[centerGy]?.[centerGx] === "rubble";
        // Rubble: #6B5B47 [107, 91, 71] | Solid Building: #2C3238 [44, 50, 56]
        return isRubble ? [107, 91, 71, 230] : [44, 50, 56, 255];
      },
      getLineColor: [32, 37, 42],
      getLineWidth: 1,
      lineWidthUnits: "pixels",
      pickable: true,
    });
  }, [osmData, terrain]);

  // 3. OSM Road Network by Classification
  const roadsLayer = useMemo(() => {
    const rList = osmData?.roads || [];
    return new PathLayer({
      id: "osm-roads",
      data: rList,
      getPath: (r: any) => r.coords.map(([gx, gy]: [number, number]) => gridToLonLat(gx, gy)),
      getColor: (r: any) => (r.class.includes("primary") || r.class.includes("trunk") ? [68, 77, 86] : [48, 55, 62]),
      getWidth: (r: any) => (r.class.includes("primary") ? 3.5 : 2.0),
      widthUnits: "pixels",
      pickable: false,
    });
  }, [osmData]);

  // 4. Belief Contour Isolines (d3-contour)
  const beliefContourLayer = useMemo(() => {
    if (!beliefHeatmap || beliefHeatmap.length === 0) return null;
    const rows = gridSize[1];
    const cols = gridSize[0];
    const flat: number[] = new Array(rows * cols);
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        flat[y * cols + x] = beliefHeatmap[y]?.[x] || 0;
      }
    }

    // Thresholds: survey contour isolines
    const contourGen = contours().size([cols, rows]).thresholds([0.15, 0.3, 0.5, 0.75]);
    const isolines = contourGen(flat);

    const paths: Array<{ path: [number, number][]; value: number }> = [];
    isolines.forEach((iso) => {
      iso.coordinates.forEach((poly) => {
        poly.forEach((ring) => {
          paths.push({
            path: ring.map((pt) => gridToLonLat(pt[0] ?? 0, pt[1] ?? 0)),
            value: iso.value,
          });
        });
      });
    });

    return new PathLayer({
      id: "belief-contours",
      data: paths,
      getPath: (d) => d.path,
      getColor: (d) => [216, 162, 74, Math.min(220, Math.round(d.value * 240 + 40))], // #D8A24A
      getWidth: 1.2,
      widthUnits: "pixels",
      pickable: false,
    });
  }, [beliefHeatmap, gridSize]);

  // 5. Foresight Ghost Futures (64 Rollout Paths)
  const foresightGhostLayer = useMemo(() => {
    if (!forecast || !forecast.candidates) return null;
    const ghostPaths: Array<{ path: [number, number][]; plan: string; dominates: boolean }> = [];
    const isDominant = Boolean(
      forecast.candidates.length > 1 &&
      forecast.candidates[0] &&
      forecast.candidates[1] &&
      forecast.candidates[0].esa_ci95[0] > forecast.candidates[1].esa_ci95[1]
    );

    // Synthesize the 64 rollout fan paths from candidates
    forecast.candidates.forEach((cand) => {
      const isCurrent = cand.plan_id === "P-current";
      Object.values(agents).forEach((ag) => {
        if (ag.route && ag.route.length > 0) {
          for (let r = 0; r < (isDominant && isCurrent ? 8 : 16); r++) {
            const jitterX = ((r % 4) - 1.5) * (isDominant ? 0.25 : 0.85);
            const jitterY = (Math.floor(r / 4) - 1.5) * (isDominant ? 0.25 : 0.85);
            const rPath: [number, number][] = [
              gridToLonLat(ag.pos[0], ag.pos[1]),
              ...ag.route.map(([gx, gy]) => gridToLonLat(gx + jitterX, gy + jitterY)),
            ];
            ghostPaths.push({ path: rPath, plan: cand.plan_id, dominates: isDominant });
          }
        }
      });
    });

    return new PathLayer({
      id: "foresight-ghosts",
      data: ghostPaths,
      getPath: (d) => d.path,
      getColor: (d) =>
        d.plan === "P-current"
          ? [216, 162, 74, d.dominates ? 45 : 22] // Tight/clear when dominant
          : [143, 163, 184, 18],
      getWidth: 1,
      widthUnits: "pixels",
    });
  }, [forecast, agents]);

  // 6. Chemical Hazard Plume with Forecast Expansion
  const plumeLayer = useMemo(() => {
    if (!plume || plume.length === 0) return null;
    const plumePolys: Array<{ polygon: [number, number][]; intensity: number }> = [];
    for (let y = 0; y < gridSize[1]; y++) {
      for (let x = 0; x < gridSize[0]; x++) {
        const val = plume[y]?.[x] || 0;
        if (val > 0.08) {
          plumePolys.push({
            polygon: [
              gridToLonLat(x, y),
              gridToLonLat(x + 1, y),
              gridToLonLat(x + 1, y + 1),
              gridToLonLat(x, y + 1),
              gridToLonLat(x, y),
            ],
            intensity: val,
          });
        }
      }
    }
    return new PolygonLayer({
      id: "chemical-plume",
      data: plumePolys,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => [180, 75, 60, Math.min(140, Math.round(d.intensity * 140))],
      getLineColor: [206, 95, 81, 80],
      getLineWidth: 1,
      lineWidthUnits: "pixels",
      stroked: true,
      filled: true,
    });
  }, [plume, gridSize]);

  // 7. Wind Flow Field Particles (Advected by Real Wind Vector)
  const windParticlesLayer = useMemo(() => {
    const rad = (wind.deg * Math.PI) / 180;
    const vx = -(wind.mps * Math.sin(rad)) * 0.15;
    const vy = -(wind.mps * Math.cos(rad)) * 0.15;

    const numParticles = 60;
    const lines: Array<{ path: [number, number][] }> = [];
    for (let i = 0; i < numParticles; i++) {
      const baseX = ((i * 7 + animTime * 4) % 60) + 2;
      const baseY = ((i * 11 + animTime * 4) % 44) + 2;
      const headX = baseX + vx;
      const headY = baseY + vy;
      lines.push({
        path: [gridToLonLat(baseX, baseY), gridToLonLat(headX, headY)],
      });
    }

    return new PathLayer({
      id: "wind-flow-field",
      data: lines,
      getPath: (d) => d.path,
      getColor: [200, 210, 220, 45],
      getWidth: 1,
      widthUnits: "pixels",
    });
  }, [wind, animTime]);

  // 8. 3D Altitude Geometry, Tethers, Shadows & Markers for ALL 5 Agents
  const agentAltBandMeters: Record<number, number> = {
    0: 0,   // Ground Rover sits on road
    1: 25,  // Scouts at 25m
    2: 35,  // Cargo at 35m
    3: 50,  // Relay at 50m
  };

  const agentList = Object.values(agents);

  // Ground Shadows (at alt 0)
  const shadowsLayer = new ScatterplotLayer({
    id: "agent-ground-shadows",
    data: agentList,
    getPosition: (a) => {
      const [lon, lat] = gridToLonLat(a.pos[0], a.pos[1]);
      return [lon, lat, 0];
    },
    getRadius: (a) => (a.alt_band === 0 ? 1.8 : 3.0),
    radiusUnits: "meters",
    getFillColor: [10, 12, 14, 180],
    getLineColor: [42, 48, 54, 200],
    getLineWidth: 1,
    lineWidthUnits: "pixels",
    stroked: true,
  });

  // Vertical Tether Lines from Ground to 3D Drone Position
  const tethersLayer = new LineLayer({
    id: "agent-tethers",
    data: agentList.filter((a) => a.alt_band > 0),
    getSourcePosition: (a) => {
      const [lon, lat] = gridToLonLat(a.pos[0], a.pos[1]);
      return [lon, lat, 0];
    },
    getTargetPosition: (a) => {
      const [lon, lat] = gridToLonLat(a.pos[0], a.pos[1]);
      const altM = agentAltBandMeters[a.alt_band] || 25;
      return [lon, lat, altM];
    },
    getColor: [115, 122, 130, 160], // #737A82 hairline tether
    getWidth: 1,
    widthUnits: "pixels",
  });

  // 3D Agent Geometry Markers
  const agentsLayer = new ScatterplotLayer({
    id: "agent-markers-3d",
    data: agentList,
    getPosition: (a) => {
      const [lon, lat] = gridToLonLat(a.pos[0], a.pos[1]);
      const altM = agentAltBandMeters[a.alt_band] || 0;
      return [lon, lat, altM];
    },
    getRadius: (a) => (a.id === selectedAgentId ? 5.5 : 4.0),
    radiusUnits: "meters",
    getFillColor: (a) => {
      if (a.id === selectedAgentId) return [216, 162, 74, 255]; // Selected #D8A24A
      if (a.status === "lost") return [206, 95, 81, 255]; // Lost #CE5F51
      if (!a.connected) return [206, 95, 81, 230]; // Comms loss
      return [116, 176, 140, 255]; // Active Fact #74B08C
    },
    getLineColor: [16, 18, 21],
    getLineWidth: 1.5,
    lineWidthUnits: "pixels",
    stroked: true,
    pickable: true,
    onClick: (info) => {
      if (info.object && onSelectAgent) {
        onSelectAgent(info.object.id === selectedAgentId ? null : info.object.id);
      }
    },
  });

  // 9. Time-Fade Trails (Last 20s) and Re-Plan Ghost Routes
  const trailsLayer = useMemo(() => {
    const lines: Array<{ path: [number, number][]; color: [number, number, number, number] }> = [];
    const hist = historyRef.current;
    const now = Date.now() / 1000;

    Object.entries(hist).forEach(([_, pts]) => {
      if (pts.length < 2) return;
      for (let i = 0; i < pts.length - 1; i++) {
        const p1 = pts[i];
        const p2 = pts[i + 1];
        if (p1 && p2) {
          const age = now - p1.t;
          const alpha = Math.max(10, Math.round(180 * (1 - age / 20)));
          lines.push({
            path: [
              gridToLonLat(p1.pos[0], p1.pos[1]),
              gridToLonLat(p2.pos[0], p2.pos[1]),
            ],
            color: [140, 125, 107, alpha], // Warm neutral time-fade
          });
        }
      }
    });

    // Re-plan ghosts for abandoned routes
    agentList.forEach((ag) => {
      if (ag.ghost_route && ag.ghost_route.length > 1) {
        lines.push({
          path: ag.ghost_route.map(([gx, gy]) => gridToLonLat(gx, gy)),
          color: [180, 100, 80, 70], // Abandoned route
        });
      }
    });

    return new PathLayer({
      id: "agent-trails",
      data: lines,
      getPath: (d) => d.path,
      getColor: (d) => d.color,
      getWidth: 1.5,
      widthUnits: "pixels",
    });
  }, [animTime, agentList]);

  // 10. Radio Mesh Arcs
  const radioArcsLayer = useMemo(() => {
    const arcs: Array<{
      source: [number, number, number];
      target: [number, number, number];
      connected: boolean;
    }> = [];

    radioEdges.forEach(([idA, idB]) => {
      const a = agents[idA];
      const b = agents[idB];
      if (a && b) {
        const [lonA, latA] = gridToLonLat(a.pos[0], a.pos[1]);
        const [lonB, latB] = gridToLonLat(b.pos[0], b.pos[1]);
        const altA = agentAltBandMeters[a.alt_band] || 0;
        const altB = agentAltBandMeters[b.alt_band] || 0;
        arcs.push({
          source: [lonA, latA, altA],
          target: [lonB, latB, altB],
          connected: a.connected && b.connected,
        });
      }
    });

    return new ArcLayer({
      id: "radio-mesh-arcs",
      data: arcs,
      getSourcePosition: (d) => d.source,
      getTargetPosition: (d) => d.target,
      getSourceColor: (d) => (d.connected ? [143, 163, 184, 150] : [206, 95, 81, 120]),
      getTargetColor: (d) => (d.connected ? [143, 163, 184, 150] : [206, 95, 81, 120]),
      getWidth: 1.5,
      widthUnits: "pixels",
    });
  }, [radioEdges, agents]);

  // 11. Survivor Detections
  const detectionsLayer = new ScatterplotLayer({
    id: "survivor-detections",
    data: detections,
    getPosition: (d) => {
      const [lon, lat] = gridToLonLat(d.cell[0], d.cell[1]);
      return [lon, lat, 0];
    },
    getRadius: 4.5,
    radiusUnits: "meters",
    getFillColor: (d) =>
      d.status === "confirmed"
        ? [116, 176, 140, 240]
        : d.status === "false_alarm"
        ? [100, 110, 120, 100]
        : [216, 162, 74, 220],
    getLineColor: [16, 18, 21],
    getLineWidth: 1.5,
    lineWidthUnits: "pixels",
    stroked: true,
  });

  const layers = [
    groundLayer,
    roadsLayer,
    buildingsLayer,
    beliefContourLayer,
    foresightGhostLayer,
    plumeLayer,
    windParticlesLayer,
    shadowsLayer,
    tethersLayer,
    trailsLayer,
    radioArcsLayer,
    detectionsLayer,
    agentsLayer,
  ].filter(Boolean);

  return (
    <div className="relative w-full h-full bg-ground overflow-hidden select-none">
      <DeckGL
        views={new MapView({ id: "vile-parle-map", controller: true, repeat: false })}
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as any)}
        layers={layers as any}
      />

      {/* Floating Map Controls & Overlays */}
      <div className="absolute top-3 left-3 flex items-center space-x-2 z-10 text-xs font-mono">
        <button
          type="button"
          onClick={handleToggleTopView}
          className={`px-2.5 py-1 border border-rule ${
            isTopView ? "bg-attention text-ground font-medium" : "bg-surface text-ink-2 hover:text-ink hover:border-rule-strong"
          }`}
          title="Switch between pitched 3D perspective and top-down plan view"
        >
          {isTopView ? "3D orbit" : "Top"}
        </button>

        <button
          type="button"
          onClick={onToggle2D}
          className="px-2.5 py-1 border border-rule bg-surface text-ink-2 hover:text-ink hover:border-rule-strong"
          title="Instant Canvas 2D fallback toggle"
        >
          2D plate
        </button>
      </div>

      {/* Real District Attribution Watermark */}
      <div className="absolute bottom-2 right-3 text-[11px] text-ink-3 font-sans pointer-events-none z-10">
        Vile Parle (West / East), Mumbai · © OpenStreetMap contributors (ODbL)
      </div>
    </div>
  );
};
