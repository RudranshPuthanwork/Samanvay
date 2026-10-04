import React, { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { MapLibreOverlay } from "@deck.gl/maplibre";
import {
  PolygonLayer,
  PathLayer,
  ScatterplotLayer,
  LineLayer,
  ArcLayer,
  TextLayer,
} from "@deck.gl/layers";
import { contours } from "d3-contour";
import { AgentState, DetectionItem, Forecast } from "../types";
import { ZoneMeta, ZoneCoordinateTransformer } from "../utils/coordinates";
import { createMumbaiMapStyle, MUMBAI_ORIENTATION_PLACES } from "../map/mapStyle";
import {
  DEFAULT_EPICENTRE,
  Epicentre,
  generateIntensityRings,
  rankDistrictsByExposure,
} from "../utils/earthquake";

// Register PMTiles protocol and worker globally once
let pmtilesProtocolRegistered = false;
function ensurePmtilesProtocol() {
  if (!pmtilesProtocolRegistered) {
    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);
    pmtilesProtocolRegistered = true;
  }
}

export interface MumbaiMapProps {
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
  // Interactivity handlers
  onInjectEvent?: ((eventType: string, params: Record<string, unknown>) => void) | undefined;
  onNoFlyPolygon?: ((polygon: [number, number][]) => void) | undefined;
  onTaskOverride?: ((taskId: string, agentId: string) => void) | undefined;
  // External camera control from log row / escalation
  focusTargetCell?: [number, number] | null | undefined;
  previewPlanRoutes?: Array<[number, number][]> | null | undefined;
}

export const MumbaiMap: React.FC<MumbaiMapProps> = ({
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
  onInjectEvent,
  onNoFlyPolygon,
  onTaskOverride,
  focusTargetCell,
  previewPlanRoutes,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const overlayRef = useRef<MapLibreOverlay | null>(null);
  const layersRef = useRef<any[]>([]);

  // View mode: "strategic" (all Mumbai) or "zone" (active 64x48 district)
  const [viewMode, setViewMode] = useState<"strategic" | "zone">("zone");

  // Zone library & active zone
  const [availableZones, setAvailableZones] = useState<ZoneMeta[]>([]);
  const [activeZoneId, setActiveZoneId] = useState<string>("vile_parle_west");
  const [activeZoneData, setActiveZoneData] = useState<any>(null);
  const [hoverZoneId, setHoverZoneId] = useState<string | null>(null);
  const [cellSizeM, setCellSizeM] = useState<number>(10.0);

  // Epicentre state for simulated intensity field (Spec §6.1.3)
  const [epicentre, setEpicentre] = useState<Epicentre>(DEFAULT_EPICENTRE);
  const [isPlacingEpicentre, setIsPlacingEpicentre] = useState(false);

  // Targeted injection state
  const [pendingInjection, setPendingInjection] = useState<string | null>(null);

  // No-fly polygon drawing state
  const [isDrawingNoFly, setIsDrawingNoFly] = useState(false);
  const [noFlyVertices, setNoFlyVertices] = useState<[number, number][]>([]);

  // Inspect state
  const [inspectedObject, setInspectedObject] = useState<{
    type: "building" | "survivor" | "agent";
    id: string;
    details: Record<string, string | number>;
  } | null>(null);
  const [hoverReadout, setHoverReadout] = useState<string | null>(null);

  // Camera presets & follow agent
  const [cameraPreset, setCameraPreset] = useState<"plan" | "oblique" | "follow">("oblique");
  const [followAgent, setFollowAgent] = useState(false);

  // Layer controls (text controls only, Spec §5.12)
  const [showBelief, setShowBelief] = useState(true);
  const [beliefOpacity, setBeliefOpacity] = useState(0.35);
  const [showGhosts, setShowGhosts] = useState(true);
  const [ghostsOpacity, setGhostsOpacity] = useState(0.20);
  const [showWind, setShowWind] = useState(true);
  const [showRadioArcs, setShowRadioArcs] = useState(true);
  const [showTrails, setShowTrails] = useState(true);

  // Performance monitoring: target 60 fps, dynamic throttle if < 30 fps
  const [fps, setFps] = useState<number>(60);
  const [isThrottled, setIsThrottled] = useState(false);
  const fpsHistoryRef = useRef<number[]>([]);
  const lastFrameTimeRef = useRef<number>(performance.now());

  // Trails position history
  const historyRef = useRef<Record<string, Array<{ pos: [number, number]; t: number }>>>({});
  const animTimeRef = useRef<number>(0);
  const [, setTick] = useState(0);

  // Coordinate transformer for active zone
  const transformer = useMemo(() => {
    const center = activeZoneData?.center || [72.8370, 19.1075];
    return new ZoneCoordinateTransformer(center[0], center[1], cellSizeM, gridSize[0], gridSize[1]);
  }, [activeZoneData, cellSizeM, gridSize]);

  // Load pre-cached zones on mount
  useEffect(() => {
    ensurePmtilesProtocol();
    fetch("/api/zones")
      .then((r) => r.json())
      .then((d) => {
        if (d?.zones?.length) {
          setAvailableZones(d.zones);
          const defaultZ = d.zones.find((z: ZoneMeta) => z.id === "vile_parle_west") || d.zones[0];
          setActiveZoneData(defaultZ);
        }
      })
      .catch(() => {
        // Fallback default Vile Parle zone
        const fallback: ZoneMeta = {
          id: "vile_parle_west",
          name: "Vile Parle West",
          description: "Near DJSCE",
          cached: true,
          estimated_damage: 0.62,
          center: [72.8370, 19.1075],
          cell_m: 10.0,
          grid: [64, 48],
          dimensions_m: [640, 480],
          utm: { zone: 43, epsg: 32643, min_east: 272128, max_east: 272768, min_north: 2113888, max_north: 2114368 },
          bbox: { west: 72.8339, south: 19.1053, east: 72.8401, north: 19.1097 },
        };
        setAvailableZones([fallback]);
        setActiveZoneData(fallback);
      });
  }, []);

  // Fetch active zone vector data when activeZoneId changes
  useEffect(() => {
    if (!activeZoneId) return;
    fetch(`/api/zones/${activeZoneId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d && d.id) {
          setActiveZoneData(d);
          if (viewMode === "zone" && mapRef.current) {
            // Fly camera to zone center (700 ms, one easing curve)
            mapRef.current.flyTo({
              center: d.center,
              zoom: 15.5,
              pitch: cameraPreset === "plan" ? 0 : 45,
              bearing: cameraPreset === "plan" ? 0 : -20,
              duration: 700,
              essential: true,
            });
          }
        }
      })
      .catch(() => {});
  }, [activeZoneId, viewMode, cameraPreset]);

  // Handle external focus target (e.g. log row click or escalation preview)
  useEffect(() => {
    if (focusTargetCell && mapRef.current) {
      const [gx, gy] = focusTargetCell;
      const [lon, lat] = transformer.gridToLonLat(gx, gy);
      mapRef.current.flyTo({
        center: [lon, lat],
        zoom: 16.5,
        duration: 700,
        essential: true,
      });
    }
  }, [focusTargetCell, transformer]);

  // Handle follow agent camera tracking
  useEffect(() => {
    if (followAgent && selectedAgentId && agents[selectedAgentId] && mapRef.current) {
      const ag = agents[selectedAgentId];
      const [lon, lat] = transformer.gridToLonLat(ag.pos[0], ag.pos[1]);
      mapRef.current.easeTo({
        center: [lon, lat],
        duration: 250,
      });
    }
  }, [followAgent, selectedAgentId, agents, transformer]);

  // Keep ref to click handlers and layers to prevent map tearing/recreation
  const clickStateRef = useRef({
    isPlacingEpicentre,
    pendingInjection,
    isDrawingNoFly,
    transformer,
    gridSize,
    onInjectEvent,
    setEpicentre,
    setIsPlacingEpicentre,
    setPendingInjection,
    setNoFlyVertices,
  });

  useEffect(() => {
    clickStateRef.current = {
      isPlacingEpicentre,
      pendingInjection,
      isDrawingNoFly,
      transformer,
      gridSize,
      onInjectEvent,
      setEpicentre,
      setIsPlacingEpicentre,
      setPendingInjection,
      setNoFlyVertices,
    };
  });

  // Initialize MapLibre GL map once on mount
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    ensurePmtilesProtocol();
    const style = createMumbaiMapStyle("/mumbai.pmtiles");

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: style as any,
      center: [72.8370, 19.1075],
      zoom: 15.5,
      pitch: 45,
      bearing: -20,
      maxPitch: 60,
      attributionControl: false,
    });

    mapRef.current = map;

    map.on("error", (e: any) => {
      console.warn("MapLibre non-fatal event:", e?.error?.message ?? e?.message ?? String(e));
    });

    // Handle WebGL context gracefully without prematurely forcing 2D
    map.getCanvas()?.addEventListener("webglcontextlost", (e: any) => {
      e.preventDefault();
      console.warn("WebGL context lost: awaiting context restore");
    });
    map.getCanvas()?.addEventListener("webglcontextrestored", () => {
      console.info("WebGL context restored");
      map.resize();
    });

    // Create MapLibreOverlay once style has loaded (critical for interleaved mode)
    map.on("load", () => {
      try {
        const overlay = new MapLibreOverlay({
          interleaved: true,
          layers: layersRef.current || [],
        });
        overlayRef.current = overlay;
        map.addControl(overlay);
        if (layersRef.current && layersRef.current.length > 0) {
          overlay.setProps({ layers: layersRef.current });
        }
        map.resize();
      } catch (err) {
        console.warn("Interleaved overlay init failed; using non-interleaved deck overlay", err);
        try {
          const overlay = new MapLibreOverlay({
            interleaved: false,
            layers: layersRef.current || [],
          });
          overlayRef.current = overlay;
          map.addControl(overlay);
          if (layersRef.current && layersRef.current.length > 0) {
            overlay.setProps({ layers: layersRef.current });
          }
        } catch (innerErr) {
          console.error("Fatal overlay error:", innerErr);
        }
      }
    });

    map.on("click", (e: any) => {
      const clickLon = e.lngLat.lng;
      const clickLat = e.lngLat.lat;
      const cur = clickStateRef.current;

      // 1. Placing Epicentre
      if (cur.isPlacingEpicentre) {
        cur.setEpicentre((prev: any) => ({ ...prev, lon: clickLon, lat: clickLat }));
        cur.setIsPlacingEpicentre(false);
        return;
      }

      // 2. Targeted event injection
      if (cur.pendingInjection) {
        const [gx, gy] = cur.transformer.lonLatToGrid(clickLon, clickLat);
        const cellX = Math.max(0, Math.min(cur.gridSize[0] - 1, Math.round(gx)));
        const cellY = Math.max(0, Math.min(cur.gridSize[1] - 1, Math.round(gy)));
        if (cur.onInjectEvent) {
          cur.onInjectEvent(cur.pendingInjection, { cell: [cellX, cellY], origin: "operator_injected" });
        }
        cur.setPendingInjection(null);
        return;
      }

      // 3. Drawing no-fly polygon
      if (cur.isDrawingNoFly) {
        const [gx, gy] = cur.transformer.lonLatToGrid(clickLon, clickLat);
        cur.setNoFlyVertices((prev: any) => [...prev, [Math.round(gx), Math.round(gy)]]);
        return;
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  // Keyboard shortcut listener (Spec §5.11)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsPlacingEpicentre(false);
        setPendingInjection(null);
        setIsDrawingNoFly(false);
        setNoFlyVertices([]);
        setInspectedObject(null);
      } else if (e.key === "f" || e.key === "F") {
        if (selectedAgentId) {
          setFollowAgent((prev) => !prev);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedAgentId]);

  // Camera choreography on escalation (Spec §6 & Phase 3 §5.8)
  useEffect(() => {
    if (!mapRef.current) return;
    if (activeEscalation && escalationTarget) {
      const [exLon, exLat] = transformer.gridToLonLat(escalationTarget[0], escalationTarget[1]);
      mapRef.current.flyTo({
        center: [exLon, exLat],
        zoom: 17.5,
        pitch: 45,
        duration: 700,
      });
    } else if (!activeEscalation && escalationTarget && activeZoneData) {
      mapRef.current.flyTo({
        center: activeZoneData.center,
        zoom: 15.5,
        pitch: cameraPreset === "plan" ? 0 : 45,
        duration: 700,
      });
    }
  }, [activeEscalation, escalationTarget, activeZoneData, cameraPreset, transformer]);

  // Animation & FPS measurement loop
  useEffect(() => {
    let animId: number;
    const loop = (now: number) => {
      animTimeRef.current = now * 0.001;
      const delta = now - lastFrameTimeRef.current;
      lastFrameTimeRef.current = now;

      if (delta > 0) {
        const curFps = Math.min(60, Math.round(1000.0 / delta));
        fpsHistoryRef.current.push(curFps);
        if (fpsHistoryRef.current.length > 30) {
          fpsHistoryRef.current.shift();
          const avgFps = Math.round(
            fpsHistoryRef.current.reduce((a, b) => a + b, 0) / fpsHistoryRef.current.length
          );
          setFps(avgFps);
          if (avgFps < 30 && !isThrottled) {
            setIsThrottled(true);
          } else if (avgFps >= 45 && isThrottled) {
            setIsThrottled(false);
          }
        }
      }

      // Record agent history for fading trails (20s window)
      const t = animTimeRef.current;
      for (const [id, ag] of Object.entries(agents)) {
        if (!historyRef.current[id]) historyRef.current[id] = [];
        const h = historyRef.current[id];
        const last = h[h.length - 1];
        if (!last || Math.hypot(last.pos[0] - ag.pos[0], last.pos[1] - ag.pos[1]) > 0.05) {
          h.push({ pos: [ag.pos[0], ag.pos[1]], t });
        }
        // Purge older than 20s
        historyRef.current[id] = h.filter((pt) => t - pt.t <= 20.0);
      }

      setTick((prev) => (prev + 1) % 1000);
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [agents, isThrottled]);

  // Construct deck.gl layers
  const layers = useMemo(() => {
    const t = animTimeRef.current;
    const resultLayers: any[] = [];

    // =========================================================================
    // STRATEGIC VIEW LAYERS (Whole Mumbai)
    // =========================================================================
    if (viewMode === "strategic") {
      // 1. Simulated Earthquake Intensity Field (Spec §6.1.3)
      const intensityRings = generateIntensityRings(epicentre, [4.5, 5.5, 6.5, 7.5, 8.2]);
      resultLayers.push(
        new PathLayer({
          id: "intensity-rings-layer",
          data: intensityRings,
          getPath: (d: any) => d.coordinates,
          getColor: (d: any) => {
            const alpha = Math.min(200, Math.max(60, (d.level / 8.5) * 180));
            return [216, 162, 74, alpha]; // attention accent with alpha
          },
          getWidth: 1.5,
          widthUnits: "pixels",
          pickable: false,
        })
      );

      // 2. Epicentre marker
      resultLayers.push(
        new ScatterplotLayer({
          id: "epicentre-marker",
          data: [epicentre],
          getPosition: (d: Epicentre) => [d.lon, d.lat, 0],
          getRadius: 280,
          getFillColor: [206, 95, 81, 220], // safety red
          getLineColor: [232, 230, 225, 255],
          lineWidthMinPixels: 2,
          stroked: true,
          filled: true,
          pickable: true,
        })
      );

      // 3. Zone footprints & hover highlights
      resultLayers.push(
        new PolygonLayer({
          id: "zone-footprints",
          data: availableZones,
          getPolygon: (z: ZoneMeta) => {
            const zt = new ZoneCoordinateTransformer(z.center[0], z.center[1], z.cell_m, z.grid[0], z.grid[1]);
            return zt.getBoundaryPolygonLonLat();
          },
          getFillColor: (z: ZoneMeta) => {
            if (z.id === activeZoneId) return [216, 162, 74, 40];
            if (z.id === hoverZoneId) return [143, 163, 184, 50];
            return [27, 32, 37, 20];
          },
          getLineColor: (z: ZoneMeta) => {
            if (z.id === activeZoneId) return [216, 162, 74, 255];
            if (z.id === hoverZoneId) return [143, 163, 184, 220];
            return [65, 74, 83, 160];
          },
          lineWidthMinPixels: 1,
          stroked: true,
          filled: true,
          pickable: true,
          onClick: (info: any) => {
            if (info?.object) {
              const clickedZ = info.object as ZoneMeta;
              setActiveZoneId(clickedZ.id);
              setViewMode("zone");
            }
          },
          onHover: (info: any) => {
            if (info?.object) {
              setHoverZoneId(info.object.id);
            } else {
              setHoverZoneId(null);
            }
          },
        })
      );

      // 4. District Orientation Labels (deck.gl TextLayer in IBM Plex Sans 12px)
      resultLayers.push(
        new TextLayer({
          id: "mumbai-orientation-labels",
          data: MUMBAI_ORIENTATION_PLACES,
          getPosition: (d: any) => [d.coordinates[0], d.coordinates[1], 5] as [number, number, number],
          getText: (d: any) => d.name,
          getSize: 12,
          getColor: (d: any) =>
            d.importance === "primary" ? [232, 230, 225, 230] : [169, 173, 177, 180],
          fontFamily: "IBM Plex Sans, sans-serif",
          fontWeight: 500,
          getTextAnchor: "middle",
          getAlignmentBaseline: "center",
          background: false,
          pickable: false,
        })
      );

      return resultLayers;
    }

    // =========================================================================
    // ZONE VIEW LAYERS (Detailed 64x48 Operating Area)
    // =========================================================================

    // 1. Outside-Zone Dimming Mask (Flat tonal step outside zone, Spec §3.4)
    const zoneBbox = transformer.getBoundsLonLat();
    const worldPoly = [
      [-180, -90],
      [180, -90],
      [180, 90],
      [-180, 90],
      [-180, -90],
    ];
    const holePoly = [
      [zoneBbox.west, zoneBbox.north],
      [zoneBbox.east, zoneBbox.north],
      [zoneBbox.east, zoneBbox.south],
      [zoneBbox.west, zoneBbox.south],
      [zoneBbox.west, zoneBbox.north],
    ];
    resultLayers.push(
      new PolygonLayer({
        id: "dim-outside-zone-layer",
        data: [{ polygon: [worldPoly, holePoly] }],
        getPolygon: (d: any) => d.polygon,
        getFillColor: [16, 18, 21, 160], // ground #101215 at flat 65% opacity
        stroked: false,
        filled: true,
        pickable: false,
      })
    );

    // 2. Zone Boundary (1 px rectangle with corner ticks, Spec §3.4)
    resultLayers.push(
      new PathLayer({
        id: "zone-boundary-rect",
        data: [{ path: transformer.getBoundaryPolygonLonLat() }],
        getPath: (d: any) => d.path,
        getColor: [216, 162, 74, 220], // attention rule
        getWidth: 1,
        widthUnits: "pixels",
        pickable: false,
      })
    );

    // 3. Extruded 3D Buildings from OSM cache with collapse / rubble styling
    const buildingsData = activeZoneData?.buildings || [];
    resultLayers.push(
      new PolygonLayer({
        id: "zone-extruded-buildings",
        data: buildingsData,
        getPolygon: (b: any) => b.lonlat || b.coords.map((c: any) => transformer.gridToLonLat(c[0], c[1])),
        getElevation: (b: any) => b.height_m || 10.0,
        extruded: true,
        wireframe: true,
        getFillColor: (b: any) => {
          // Check if building has collapsed into rubble in simulation terrain
          const gx = Math.round(b.coords?.[0]?.[0] || 0);
          const gy = Math.round(b.coords?.[0]?.[1] || 0);
          const cellType = terrain?.[gy]?.[gx];
          if (cellType === "rubble") return [107, 91, 71, 230]; // rubble token
          return [44, 50, 56, 220]; // building token #2C3238
        },
        getLineColor: [65, 74, 83, 200], // rule-strong outline
        lineWidthMinPixels: 1,
        pickable: true,
        onClick: (info: any) => {
          if (info?.object) {
            const b = info.object;
            setInspectedObject({
              type: "building",
              id: b.id,
              details: {
                height: `${b.height_m} m`,
                levels: b.levels || 2,
                type: b.type || "commercial",
                damage_class: "moderate (grade 2)",
                collapse_prob: "0.12",
                belief_mass: "0.04",
              },
            });
          }
        },
        onHover: (info: any) => {
          if (info?.object) {
            const b = info.object;
            setHoverReadout(`Bldg ${b.id}: h=${b.height_m}m, levels=${b.levels}`);
          } else {
            setHoverReadout(null);
          }
        },
      })
    );

    // 4. Bayesian Search Belief Contours (d3-contour)
    if (showBelief && beliefHeatmap && beliefHeatmap.length > 0) {
      try {
        const flatBelief: number[] = [];
        for (let y = 0; y < gridSize[1]; y++) {
          for (let x = 0; x < gridSize[0]; x++) {
            flatBelief.push(beliefHeatmap[y]?.[x] || 0);
          }
        }
        const contourGen = contours().size([gridSize[0], gridSize[1]]).thresholds([0.15, 0.35, 0.60, 0.85]);
        const contourSeries = contourGen(flatBelief);
        const contourPolygons: any[] = [];

        for (const c of contourSeries) {
          for (const poly of c.coordinates) {
            for (const ring of poly) {
              const lonLatRing = ring.map((pt: any) =>
                transformer.gridToLonLat(Number(pt[0]) || 0, Number(pt[1]) || 0)
              );
              contourPolygons.push({ value: c.value, ring: lonLatRing });
            }
          }
        }

        resultLayers.push(
          new PolygonLayer({
            id: "belief-contour-fills",
            data: contourPolygons,
            getPolygon: (d: any) => d.ring,
            getFillColor: (d: any) => [216, 162, 74, Math.round(d.value * beliefOpacity * 180)],
            getLineColor: (d: any) => [216, 162, 74, Math.round(d.value * 255)],
            lineWidthMinPixels: 1,
            stroked: true,
            filled: true,
            pickable: false,
          })
        );
      } catch (err) {
        // Fallback gracefully
      }
    }

    // 5. Toxic Chemical Plume Concentration Field
    if (plume && plume.length > 0) {
      const plumeCells: any[] = [];
      for (let y = 0; y < gridSize[1]; y++) {
        for (let x = 0; x < gridSize[0]; x++) {
          const conc = plume[y]?.[x] || 0;
          if (conc > 0.05) {
            const [lon, lat] = transformer.gridToLonLat(x, y);
            plumeCells.push({ lon, lat, conc });
          }
        }
      }

      resultLayers.push(
        new ScatterplotLayer({
          id: "plume-particles-layer",
          data: plumeCells,
          getPosition: (d: any) => [d.lon, d.lat, 1] as [number, number, number],
          getRadius: cellSizeM * 0.7,
          getFillColor: (d: any) => {
            const alpha = Math.min(220, Math.round(d.conc * 190));
            return d.conc >= 0.5 ? [206, 95, 81, alpha] : [143, 163, 184, alpha];
          },
          pickable: false,
        })
      );
    }

    // 6. Ghost Futures (Monte Carlo Rollout Ensembles, Spec §6.5 & Phase 3 §6)
    if (showGhosts && forecast?.candidates) {
      const ghostPaths: any[] = [];
      const rolloutsToShow = isThrottled ? 8 : 16;
      const isDominant = Boolean(
        forecast.candidates.length > 1 &&
          forecast.candidates[0] &&
          forecast.candidates[1] &&
          forecast.candidates[0].esa_ci95[0] > forecast.candidates[1].esa_ci95[1]
      );

      forecast.candidates.forEach((cand) => {
        const isCurrent = cand.plan_id === "P-current";
        Object.values(agents).forEach((ag) => {
          if (ag.route && ag.route.length > 0) {
            for (let r = 0; r < (isDominant && isCurrent ? 4 : rolloutsToShow); r++) {
              const jitterX = ((r % 4) - 1.5) * (isDominant ? 0.25 : 0.85);
              const jitterY = (Math.floor(r / 4) - 1.5) * (isDominant ? 0.25 : 0.85);
              const rPath: [number, number][] = [
                transformer.gridToLonLat(ag.pos[0], ag.pos[1]),
                ...ag.route.map(([gx, gy]) => transformer.gridToLonLat(gx + jitterX, gy + jitterY)),
              ];
              ghostPaths.push({ path: rPath, plan: cand.plan_id, dominates: isDominant });
            }
          }
        });
      });

      resultLayers.push(
        new PathLayer({
          id: "ghost-futures-layer",
          data: ghostPaths,
          getPath: (d: any) => d.path,
          getColor: (d: any) =>
            d.plan === "P-current"
              ? [216, 162, 74, Math.round(ghostsOpacity * 255)]
              : [143, 163, 184, Math.round(ghostsOpacity * 120)],
          getWidth: 1,
          widthUnits: "pixels",
          pickable: false,
        })
      );
    }

    // 7. Preview Plan Routes (Escalation dialog hover/focus preview, Spec §5.8)
    if (previewPlanRoutes && previewPlanRoutes.length > 0) {
      const previewData = previewPlanRoutes.map((rt) => ({
        path: rt.map((pt) => transformer.gridToLonLat(pt[0], pt[1])),
      }));
      resultLayers.push(
        new PathLayer({
          id: "escalation-preview-routes",
          data: previewData,
          getPath: (d: any) => d.path,
          getColor: [216, 162, 74, 240], // attention gold
          getWidth: 2.5,
          widthUnits: "pixels",
          pickable: false,
        })
      );
    }

    // 8. Fading Trails (20s time-decay in warm neutral, Spec §6)
    if (showTrails) {
      const trailPaths: any[] = [];
      for (const [id, pts] of Object.entries(historyRef.current)) {
        if (pts.length > 1) {
          const pathLonLat = pts.map((p) => transformer.gridToLonLat(p.pos[0], p.pos[1]));
          const isSelected = id === selectedAgentId;
          trailPaths.push({ id, path: pathLonLat, isSelected });
        }
      }
      resultLayers.push(
        new PathLayer({
          id: "agent-fading-trails",
          data: trailPaths,
          getPath: (d: any) => d.path,
          getColor: (d: any) =>
            d.isSelected ? [216, 162, 74, 200] : [201, 185, 154, 110], // warm neutral #C9B99A fade
          getWidth: 1.5,
          widthUnits: "pixels",
          pickable: false,
        })
      );
    }

    // 9. Multi-hop Radio Mesh Arcs (Spec §6)
    if (showRadioArcs && radioEdges && radioEdges.length > 0) {
      const arcData = radioEdges
        .map(([id1, id2]) => {
          const p1 = id1 === "base" ? [2, 2] : agents[id1]?.pos;
          const p2 = id2 === "base" ? [2, 2] : agents[id2]?.pos;
          if (!p1 || !p2 || !p1[0] || !p1[1] || !p2[0] || !p2[1]) return null;
          return {
            source: transformer.gridToLonLat(p1[0], p1[1]),
            target: transformer.gridToLonLat(p2[0], p2[1]),
          };
        })
        .filter((a): a is { source: [number, number]; target: [number, number] } => a !== null);

      resultLayers.push(
        new ArcLayer({
          id: "radio-mesh-arcs",
          data: arcData,
          getSourcePosition: (d: any) => [d.source[0], d.source[1], 5] as [number, number, number],
          getTargetPosition: (d: any) => [d.target[0], d.target[1], 5] as [number, number, number],
          getSourceColor: [143, 163, 184, 180], // slate policy token
          getTargetColor: [116, 176, 140, 180],
          getWidth: 1.5,
          getHeight: 0.15,
          pickable: false,
        })
      );
    }

    // 9.5 Wind Flow Field Particles (Advected by Real Wind Vector)
    if (showWind && wind) {
      const rad = (wind.deg * Math.PI) / 180;
      const vx = -(wind.mps * Math.sin(rad)) * 0.15;
      const vy = -(wind.mps * Math.cos(rad)) * 0.15;

      const numParticles = isThrottled ? 25 : 60;
      const lines: Array<{ path: [number, number][] }> = [];
      for (let i = 0; i < numParticles; i++) {
        const baseX = ((i * 7 + t * 4) % (gridSize[0] - 4)) + 2;
        const baseY = ((i * 11 + t * 4) % (gridSize[1] - 4)) + 2;
        const headX = baseX + vx;
        const headY = baseY + vy;
        lines.push({
          path: [transformer.gridToLonLat(baseX, baseY), transformer.gridToLonLat(headX, headY)],
        });
      }

      resultLayers.push(
        new PathLayer({
          id: "wind-flow-field",
          data: lines,
          getPath: (d: any) => d.path,
          getColor: [200, 210, 220, 50],
          getWidth: 1,
          widthUnits: "pixels",
          pickable: false,
        })
      );
    }

    // 10. Detections & Survivor Markers (posterior, urgency)
    resultLayers.push(
      new ScatterplotLayer({
        id: "survivor-markers-layer",
        data: detections,
        getPosition: (d: DetectionItem) => {
          const [lon, lat] = transformer.gridToLonLat(d.cell[0], d.cell[1]);
          return [lon, lat, 2] as [number, number, number];
        },
        getRadius: cellSizeM * 0.45,
        getFillColor: (d: DetectionItem) =>
          d.urgency === "critical"
            ? [206, 95, 81, 230]
            : d.urgency === "serious"
            ? [216, 162, 74, 220]
            : [116, 176, 140, 200],
        getLineColor: [232, 230, 225, 255],
        lineWidthMinPixels: 1.5,
        stroked: true,
        filled: true,
        pickable: true,
        onClick: (info: any) => {
          if (info?.object) {
            const s = info.object as DetectionItem;
            setInspectedObject({
              type: "survivor",
              id: s.id,
              details: {
                urgency: s.urgency || "unknown",
                posterior: s.posterior.toFixed(2),
                status: s.status,
              },
            });
          }
        },
      })
    );

    // 11. Swarm Agents (5 agents with 3D altitude tethers, ground shadows, and status)
    const agentList = Object.entries(agents).map(([agentKey, st]) => ({
      agentId: agentKey,
      ...st,
      lonlat: transformer.gridToLonLat(st.pos[0], st.pos[1]),
      altM: st.type.startsWith("scout") ? 22 : st.type === "cargo" ? 18 : st.type === "relay" ? 35 : 0,
      isSelected: agentKey === selectedAgentId,
    }));

    // 11a. Ground shadows & altitude tethers
    resultLayers.push(
      new LineLayer({
        id: "agent-altitude-tethers",
        data: agentList.filter((a) => a.altM > 0),
        getSourcePosition: (d: any) => [d.lonlat[0], d.lonlat[1], 0] as [number, number, number],
        getTargetPosition: (d: any) => [d.lonlat[0], d.lonlat[1], d.altM] as [number, number, number],
        getColor: (d: any) => (d.isSelected ? [216, 162, 74, 220] : [65, 74, 83, 140]),
        getWidth: 1,
        widthUnits: "pixels",
      })
    );

    resultLayers.push(
      new ScatterplotLayer({
        id: "agent-ground-shadows",
        data: agentList.filter((a) => a.altM > 0),
        getPosition: (d: any) => [d.lonlat[0], d.lonlat[1], 0.5] as [number, number, number],
        getRadius: cellSizeM * 0.35,
        getFillColor: [16, 18, 21, 140],
        pickable: false,
      })
    );

    // 11b. Agent Markers at Flight Altitude
    resultLayers.push(
      new ScatterplotLayer({
        id: "agent-markers-3d",
        data: agentList,
        getPosition: (d: any) => [d.lonlat[0], d.lonlat[1], d.altM] as [number, number, number],
        getRadius: cellSizeM * 0.5,
        getFillColor: (d: any) => {
          if (d.agentId === "scout-1") return [183, 196, 207, 255];
          if (d.agentId === "scout-2") return [201, 185, 154, 255];
          if (d.agentId === "cargo-1") return [159, 191, 168, 255];
          if (d.agentId === "rover-1") return [191, 163, 160, 255];
          return [168, 178, 188, 255];
        },
        getLineColor: (d: any) =>
          d.isSelected ? [216, 162, 74, 255] : d.battery <= 20 ? [206, 95, 81, 255] : [232, 230, 225, 200],
        lineWidthMinPixels: 1.5,
        stroked: true,
        filled: true,
        pickable: true,
        onClick: (info: any) => {
          if (info?.object && onSelectAgent) {
            onSelectAgent(info.object.agentId);
            setInspectedObject({
              type: "agent",
              id: info.object.agentId,
              details: {
                type: info.object.type,
                status: info.object.status,
                battery: `${Math.round(info.object.battery)}%`,
                reserve_floor: `${Math.round(info.object.reserve_required || 20)}%`,
                connected: info.object.connected ? "connected" : "radio silent",
                lease_remaining: `${Math.round(info.object.lease?.expires_t || 0)} s`,
              },
            });
          }
        },
      })
    );

    // 12. Drawn No-Fly Polygon preview (Spec §5.6)
    if (noFlyVertices.length >= 2) {
      const noFlyLonLat = noFlyVertices.map((v) => transformer.gridToLonLat(v[0], v[1]));
      resultLayers.push(
        new PathLayer({
          id: "drawing-nofly-path",
          data: [{ path: noFlyLonLat }],
          getPath: (d: any) => d.path,
          getColor: [206, 95, 81, 230], // safety red
          getWidth: 2,
          widthUnits: "pixels",
        })
      );
    }

    return resultLayers;
  }, [
    viewMode,
    epicentre,
    availableZones,
    activeZoneId,
    hoverZoneId,
    activeZoneData,
    transformer,
    terrain,
    showBelief,
    beliefHeatmap,
    gridSize,
    beliefOpacity,
    plume,
    cellSizeM,
    showGhosts,
    forecast,
    isThrottled,
    ghostsOpacity,
    previewPlanRoutes,
    showTrails,
    selectedAgentId,
    showRadioArcs,
    radioEdges,
    showWind,
    wind,
    agents,
    detections,
    noFlyVertices,
    onSelectAgent,
  ]);

  // Update deck.gl overlay layers when layers change
  useEffect(() => {
    layersRef.current = layers;
    if (overlayRef.current) {
      overlayRef.current.setProps({ layers });
    }
  }, [layers]);

  // Ranked districts around epicentre
  const rankedDistricts = useMemo(() => {
    return rankDistrictsByExposure(epicentre, availableZones);
  }, [epicentre, availableZones]);

  return (
    <div className="relative w-full h-full overflow-hidden select-none bg-ground font-sans">
      {/* MapLibre WebGL Canvas Container */}
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Top Left Control Surface & Mode Switch */}
      <div className="absolute top-2 left-2 z-20 flex flex-col gap-1.5 pointer-events-auto">
        <div className="flex items-center gap-1 bg-surface border border-rule px-2 py-1">
          <button
            onClick={() => {
              setViewMode("strategic");
              if (mapRef.current) {
                mapRef.current.flyTo({
                  center: [72.89, 19.10],
                  zoom: 10.8,
                  pitch: 0,
                  bearing: 0,
                  duration: 700,
                  essential: true,
                });
              }
            }}
            className={`px-2 py-0.5 text-xs font-mono transition-colors ${
              viewMode === "strategic"
                ? "bg-surface-raised text-ink font-medium"
                : "text-ink-3 hover:text-ink"
            }`}
          >
            Strategic (Mumbai)
          </button>
          <span className="text-rule">|</span>
          <button
            onClick={() => {
              setViewMode("zone");
              if (mapRef.current && activeZoneData) {
                mapRef.current.flyTo({
                  center: activeZoneData.center,
                  zoom: 15.5,
                  pitch: 45,
                  bearing: -20,
                  duration: 700,
                  essential: true,
                });
              }
            }}
            className={`px-2 py-0.5 text-xs font-mono transition-colors ${
              viewMode === "zone"
                ? "bg-surface-raised text-ink font-medium"
                : "text-ink-3 hover:text-ink"
            }`}
          >
            Zone: {activeZoneData?.name || "Vile Parle West"}
          </button>
          <span className="text-rule">|</span>
          <button
            onClick={onToggle2D}
            className="px-2 py-0.5 text-xs text-ink-3 hover:text-ink border border-transparent"
          >
            2D plate
          </button>
        </div>

        {/* Strategic View: Damage Ranking & Epicentre Placement */}
        {viewMode === "strategic" && (
          <div className="w-80 bg-surface border border-rule p-2.5 flex flex-col gap-2">
            <div className="flex items-center justify-between border-b border-rule pb-1.5">
              <span className="text-xs font-semibold text-ink">Earthquake intensity</span>
              <span className="text-[11px] font-mono text-attention">simulated §6.1.3</span>
            </div>
            <div className="text-[11px] text-ink-2">
              City-scale decay length <span className="font-mono text-ink">d₀=7.5 km</span> [ASSUMPTION].
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlacingEpicentre(true)}
                className={`px-2 py-1 text-xs border ${
                  isPlacingEpicentre
                    ? "bg-surface-raised text-attention font-medium border-attention"
                    : "bg-surface-raised border-rule text-ink hover:border-rule-strong"
                }`}
              >
                {isPlacingEpicentre ? "Click map to place epicentre" : "Move epicentre"}
              </button>
              <span className="text-[11px] font-mono text-ink-2">
                M{epicentre.magnitude} · MMI {epicentre.intensity_i0}
              </span>
            </div>

            {/* Ranked Districts */}
            <div className="mt-1">
              <div className="text-[11px] text-ink-3 font-mono mb-1">
                District damage exposure ranking
              </div>
              <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
                {rankedDistricts.map((d, idx) => (
                  <div
                    key={d.id}
                    onClick={() => {
                      setActiveZoneId(d.id);
                      setViewMode("zone");
                    }}
                    onMouseEnter={() => setHoverZoneId(d.id)}
                    onMouseLeave={() => setHoverZoneId(null)}
                    className={`flex items-center justify-between px-2 py-1 cursor-pointer border text-xs ${
                      d.id === activeZoneId
                        ? "border-attention bg-surface-raised text-ink"
                        : "border-transparent hover:border-rule text-ink-2 hover:text-ink"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[11px] text-ink-3">{idx + 1}.</span>
                      <span className="font-medium">{d.name}</span>
                      {d.cached ? (
                        <span className="text-[10px] font-mono text-fact">cached</span>
                      ) : (
                        <span className="text-[10px] font-mono text-ink-3">offline</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span>MMI {d.intensity_mmi}</span>
                      <span className={d.damage_exposure > 0.7 ? "text-safety font-bold" : "text-attention"}>
                        {(d.damage_exposure * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Operating Zone View: Zone Controls & Cell Size */}
        {viewMode === "zone" && (
          <div className="flex items-center gap-2 bg-surface border border-rule px-2 py-1 text-xs">
            <span className="text-ink-3">Cell size:</span>
            {[10, 15, 20].map((sz) => (
              <button
                key={sz}
                onClick={() => setCellSizeM(sz)}
                className={`px-1.5 py-0.5 font-mono ${
                  cellSizeM === sz
                    ? "bg-surface-raised border border-attention text-attention font-bold"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                {sz} m
              </button>
            ))}
            <span className="text-rule">|</span>
            <span className="font-mono text-ink-2">
              {gridSize[0] * cellSizeM} × {gridSize[1] * cellSizeM} m
            </span>
          </div>
        )}

        {/* Targeted Event Injection Controls (Spec §5.3) */}
        {viewMode === "zone" && (
          <div className="bg-surface border border-rule p-2 flex flex-col gap-1.5">
            <div className="flex items-center justify-between border-b border-rule pb-1">
              <span className="text-xs font-semibold text-ink">Targeted event injection</span>
              {pendingInjection && (
                <button
                  onClick={() => setPendingInjection(null)}
                  className="text-[10px] text-ink-3 hover:text-ink font-mono"
                >
                  cancel [Esc]
                </button>
              )}
            </div>
            {pendingInjection ? (
              <div className="text-[11px] font-mono text-attention">
                Targeting: click cell or agent to inject {pendingInjection}
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-1">
                {[
                  "AFTERSHOCK",
                  "DETECTION",
                  "COMMS_LOSS",
                  "BATTERY_FAULT",
                  "AGENT_FAILURE",
                  "WEATHER_CHANGE",
                ].map((ev) => (
                  <button
                    key={ev}
                    onClick={() => setPendingInjection(ev)}
                    className="px-1.5 py-1 text-[11px] font-mono text-left bg-surface-raised border border-rule text-ink-2 hover:text-ink hover:border-rule-strong"
                  >
                    {ev.replace("_", " ")}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Geofence / No-Fly Polygon Drawer (Spec §5.6) */}
        {viewMode === "zone" && (
          <div className="flex items-center gap-1.5 bg-surface border border-rule px-2 py-1 text-xs">
            {!isDrawingNoFly ? (
              <button
                onClick={() => {
                  setIsDrawingNoFly(true);
                  setNoFlyVertices([]);
                }}
                className="text-ink-2 hover:text-ink font-medium"
              >
                Draw no-fly polygon
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="font-mono text-attention text-[11px]">
                  Vertices: {noFlyVertices.length} (click map)
                </span>
                <button
                  onClick={() => {
                    if (noFlyVertices.length >= 3 && onNoFlyPolygon) {
                      onNoFlyPolygon(noFlyVertices);
                    }
                    setIsDrawingNoFly(false);
                    setNoFlyVertices([]);
                  }}
                  className="px-2 py-0.5 bg-surface-raised border border-rule-strong hover:border-attention text-ink font-mono text-[11px]"
                >
                  Apply
                </button>
                <button
                  onClick={() => {
                    setIsDrawingNoFly(false);
                    setNoFlyVertices([]);
                  }}
                  className="text-ink-3 hover:text-ink text-[11px]"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Top Right: Layer Controls & Camera Presets */}
      <div className="absolute top-2 right-2 z-20 flex flex-col gap-1.5 pointer-events-auto items-end">
        {/* Camera Presets (Spec §5.11) */}
        <div className="flex items-center gap-1 bg-surface border border-rule px-2 py-1 text-xs">
          <span className="text-ink-3 text-[11px]">Camera:</span>
          {(["plan", "oblique"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => {
                setCameraPreset(mode);
                setFollowAgent(false);
                if (mapRef.current) {
                  mapRef.current.easeTo({
                    pitch: mode === "plan" ? 0 : 45,
                    bearing: mode === "plan" ? 0 : -20,
                    duration: 500,
                  });
                }
              }}
              className={`px-1.5 py-0.5 font-medium ${
                cameraPreset === mode && !followAgent
                  ? "bg-surface-raised border border-rule-strong text-ink font-bold"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              {mode}
            </button>
          ))}
          <button
            onClick={() => setFollowAgent((prev) => !prev)}
            disabled={!selectedAgentId}
            className={`px-1.5 py-0.5 font-medium ${
              followAgent
                ? "bg-surface-raised border border-attention text-attention font-bold"
                : selectedAgentId
                ? "text-ink-2 hover:text-ink"
                : "text-ink-3 opacity-50 cursor-not-allowed"
            }`}
          >
            Follow [F]
          </button>
          <button
            onClick={() => {
              if (mapRef.current && activeZoneData) {
                mapRef.current.flyTo({
                  center: activeZoneData.center,
                  zoom: 15.5,
                  duration: 600,
                });
              }
            }}
            className="px-1.5 py-0.5 text-ink-2 hover:text-ink"
          >
            Frame all
          </button>
        </div>

        {/* Text-Only Layer Controls & Opacity (Spec §5.12) */}
        {viewMode === "zone" && (
          <div className="bg-surface border border-rule p-2 text-xs flex flex-col gap-1.5 w-56">
            <span className="font-semibold text-ink text-[11px] border-b border-rule pb-1">
              Layer controls
            </span>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-1.5 text-ink-2">
                <input
                  type="checkbox"
                  checked={showBelief}
                  onChange={(e) => setShowBelief(e.target.checked)}
                  className="rounded-none bg-surface border-rule"
                />
                Belief isolines
              </label>
              <input
                type="range"
                min="0.1"
                max="0.8"
                step="0.05"
                value={beliefOpacity}
                onChange={(e) => setBeliefOpacity(parseFloat(e.target.value))}
                className="w-16 accent-attention"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-1.5 text-ink-2">
                <input
                  type="checkbox"
                  checked={showGhosts}
                  onChange={(e) => setShowGhosts(e.target.checked)}
                  className="rounded-none bg-surface border-rule"
                />
                Ghost futures
              </label>
              <input
                type="range"
                min="0.05"
                max="0.5"
                step="0.05"
                value={ghostsOpacity}
                onChange={(e) => setGhostsOpacity(parseFloat(e.target.value))}
                className="w-16 accent-attention"
              />
            </div>
            <div className="flex items-center justify-between text-ink-2">
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showRadioArcs}
                  onChange={(e) => setShowRadioArcs(e.target.checked)}
                  className="rounded-none bg-surface border-rule"
                />
                Radio mesh arcs
              </label>
            </div>
            <div className="flex items-center justify-between text-ink-2">
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showTrails}
                  onChange={(e) => setShowTrails(e.target.checked)}
                  className="rounded-none bg-surface border-rule"
                />
                Fading trails
              </label>
            </div>
            <div className="flex items-center justify-between text-ink-2">
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showWind}
                  onChange={(e) => setShowWind(e.target.checked)}
                  className="rounded-none bg-surface border-rule"
                />
                Wind flow
              </label>
            </div>
          </div>
        )}

        {/* FPS & Performance Status Line (Spec §7) */}
        <div className="bg-surface border border-rule px-2 py-0.5 text-[11px] font-mono flex items-center gap-2">
          <span className={fps < 30 ? "text-safety font-bold" : "text-fact"}>{fps} fps</span>
          {isThrottled && <span className="text-attention">throttled to maintain 30+ fps</span>}
        </div>
      </div>

      {/* Flat Readout Box for Inspected Building / Survivor / Agent (No Tooltip Bubble, Spec §5.5) */}
      {inspectedObject && (
        <div className="absolute bottom-10 right-2 z-30 w-72 bg-surface border border-rule p-3 pointer-events-auto">
          <div className="flex items-center justify-between border-b border-rule pb-1.5 mb-2">
            <span className="text-xs font-bold text-ink">
              {inspectedObject.type}: {inspectedObject.id}
            </span>
            <button
              onClick={() => setInspectedObject(null)}
              className="text-xs text-ink-3 hover:text-ink font-mono"
            >
              [close]
            </button>
          </div>
          <div className="flex flex-col gap-1 text-xs">
            {Object.entries(inspectedObject.details).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span className="text-ink-3 font-mono">{k.replace("_", " ")}:</span>
                <span className="font-mono text-ink">{String(v)}</span>
              </div>
            ))}
          </div>

          {/* Operator Override Action for Survivor Task */}
          {inspectedObject.type === "survivor" && onTaskOverride && (
            <div className="mt-2.5 pt-2 border-t border-rule flex flex-col gap-1">
              <span className="text-[11px] text-ink-2 font-mono">Assign task to agent:</span>
              <div className="flex gap-1">
                {Object.keys(agents).map((aid) => (
                  <button
                    key={aid}
                    onClick={() => {
                      onTaskOverride(String(inspectedObject.details.assigned_task), aid);
                      setInspectedObject(null);
                    }}
                    className="px-1.5 py-0.5 text-[10px] font-mono bg-surface-raised border border-rule hover:border-attention text-ink"
                  >
                    {aid.slice(0, 7)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Flat Hover Readout */}
      {hoverReadout && !inspectedObject && (
        <div className="absolute bottom-10 left-2 z-20 bg-surface border border-rule px-2 py-1 text-[11px] font-mono text-ink pointer-events-none">
          {hoverReadout}
        </div>
      )}

      {/* Scale Bar and Attribution in Lower Left (Spec §3.5) */}
      <div className="absolute bottom-0 left-0 z-10 flex items-center gap-3 bg-surface border-t border-r border-rule px-2 py-0.5 text-[12px] text-ink-3 pointer-events-none select-none">
        <span>© OpenStreetMap contributors (ODbL) · Protomaps</span>
        {viewMode === "zone" && (
          <span className="font-mono">
            Scale: 1 cell = {cellSizeM} m · 64×48 ({gridSize[0] * cellSizeM}×{gridSize[1] * cellSizeM} m)
          </span>
        )}
      </div>
    </div>
  );
};
