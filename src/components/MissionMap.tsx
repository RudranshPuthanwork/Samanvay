import React, { useEffect, useRef, useState } from "react";
import { AgentState, DetectionItem, Forecast } from "../types";
import { MumbaiMap } from "./MumbaiMap";

export interface MissionMapProps {
  gridSize: [number, number];
  terrain: string[][];
  plume: number[][];
  beliefHeatmap: number[][];
  agents: Record<string, AgentState>;
  detections: DetectionItem[];
  radioEdges: [string, string][];
  forecast?: Forecast | null;
  wind?: { deg: number; mps: number };
  activeEscalation?: boolean;
  escalationTarget?: [number, number] | null;
  selectedAgentId?: string | null | undefined;
  onSelectAgent?: ((id: string | null) => void) | undefined;
  onInjectEvent?: ((eventType: string, params: Record<string, unknown>) => void) | undefined;
  onNoFlyPolygon?: ((polygon: [number, number][]) => void) | undefined;
  onTaskOverride?: ((taskId: string, agentId: string) => void) | undefined;
  focusTargetCell?: [number, number] | null | undefined;
  previewPlanRoutes?: [number, number][][] | null | undefined;
}

export const MissionMap: React.FC<MissionMapProps> = ({
  gridSize,
  terrain,
  plume,
  beliefHeatmap,
  agents,
  detections,
  radioEdges,
  forecast,
  wind,
  activeEscalation,
  escalationTarget,
  selectedAgentId,
  onSelectAgent,
  onInjectEvent,
  onNoFlyPolygon,
  onTaskOverride,
  focusTargetCell,
  previewPlanRoutes,
}) => {
  const [use3d, setUse3d] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoverCell, setHoverCell] = useState<{ x: number; y: number; val?: string } | null>(null);

  // Layer toggles for 2D plate fallback
  const [layers, setLayers] = useState({
    belief: true,
    plume: true,
    radio: true,
    routes: true,
  });

  const toggleLayer = (key: keyof typeof layers) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    if (use3d) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const cols = gridSize[0];
    const rows = gridSize[1];
    const cellW = width / cols;
    const cellH = height / rows;

    ctx.clearRect(0, 0, width, height);

    // 1. Draw Terrain
    const terrainColors: Record<string, string> = {
      road: "#3A424A",
      open: "#1B2025",
      building: "#2C3238",
      rubble: "#6B5B47",
      water: "#2E4A5A",
      base: "#101215",
    };

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const tType = terrain[y]?.[x] || "open";
        ctx.fillStyle = terrainColors[tType] || "#1B2025";
        ctx.fillRect(x * cellW, y * cellH, cellW, cellH);

        // 1px hairline between road and block
        if (tType === "road") {
          ctx.strokeStyle = "#2A3036";
          ctx.lineWidth = 1;
          ctx.strokeRect(x * cellW, y * cellH, cellW, cellH);
        }
      }
    }

    // 2. Draw Belief Heatmap (single-hue ramp to #D8A24A)
    if (layers.belief && beliefHeatmap.length > 0) {
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const prob = beliefHeatmap[y]?.[x] || 0;
          if (prob > 0.05) {
            ctx.fillStyle = `rgba(216, 162, 74, ${Math.min(0.45, prob * 0.6)})`;
            ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
          }
        }
      }
    }

    // 3. Draw Plume (chemical hazard)
    if (layers.plume && plume.length > 0) {
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const val = plume[y]?.[x] || 0;
          if (val > 0.1) {
            ctx.fillStyle = `rgba(206, 95, 81, ${Math.min(0.55, val * 0.7)})`;
            ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
          }
        }
      }
    }

    // 4. Draw Radio Links
    if (layers.radio) {
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);

      radioEdges.forEach(([src, dst]) => {
        const getCoord = (id: string): [number, number] => {
          if (id === "base") return [2, 2];
          const ag = agents[id];
          return ag ? ag.pos : [2, 2];
        };
        const p1 = getCoord(src);
        const p2 = getCoord(dst);

        ctx.strokeStyle = "#737A82";
        ctx.beginPath();
        ctx.moveTo((p1[0] + 0.5) * cellW, (p1[1] + 0.5) * cellH);
        ctx.lineTo((p2[0] + 0.5) * cellW, (p2[1] + 0.5) * cellH);
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 5. Draw Agent Planned Routes
    if (layers.routes) {
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);

      Object.values(agents).forEach((ag) => {
        if (!ag.route || ag.route.length === 0) return;
        const isSel = ag.id === selectedAgentId;
        ctx.strokeStyle = isSel ? "#D8A24A" : "#8FA3B8";

        ctx.beginPath();
        ctx.moveTo((ag.pos[0] + 0.5) * cellW, (ag.pos[1] + 0.5) * cellH);
        ag.route.forEach(([rx, ry]) => {
          ctx.lineTo((rx + 0.5) * cellW, (ry + 0.5) * cellH);
        });
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 6. Draw Detections
    detections.forEach((det) => {
      const dx = (det.cell[0] + 0.5) * cellW;
      const dy = (det.cell[1] + 0.5) * cellH;

      ctx.fillStyle = "#CE5F51";
      ctx.fillRect(dx - 4, dy - 4, 8, 8);
      ctx.strokeStyle = "#E8E6E1";
      ctx.lineWidth = 1;
      ctx.strokeRect(dx - 4, dy - 4, 8, 8);

      if (det.urgency) {
        ctx.fillStyle = "#E8E6E1";
        ctx.font = '10px "IBM Plex Mono"';
        ctx.fillText(det.urgency.slice(0, 4), dx + 6, dy + 3);
      }
    });

    // 7. Draw Agents with Canvas Symbols (Spec §6.2)
    const agentList = Object.values(agents);
    const cellGroups: Record<string, string[]> = {};
    agentList.forEach((ag) => {
      const key = `${ag.pos[0]},${ag.pos[1]}`;
      if (!cellGroups[key]) cellGroups[key] = [];
      cellGroups[key].push(ag.id);
    });

    agentList.forEach((ag) => {
      const key = `${ag.pos[0]},${ag.pos[1]}`;
      const group = cellGroups[key] || [ag.id];
      const idxInGroup = group.indexOf(ag.id);
      const offsetPx = group.length > 1 ? (idxInGroup - (group.length - 1) / 2) * 8 : 0;

      const cx = (ag.pos[0] + 0.5) * cellW + offsetPx;
      const cy = (ag.pos[1] + 0.5) * cellH;
      const isSel = ag.id === selectedAgentId;

      ctx.fillStyle = isSel ? "#D8A24A" : "#E8E6E1";
      ctx.strokeStyle = isSel ? "#D8A24A" : "#101215";
      ctx.lineWidth = 1.5;

      const typeId = ag.type;
      if (typeId.includes("scout")) {
        // Upward triangle
        ctx.beginPath();
        ctx.moveTo(cx, cy - 7);
        ctx.lineTo(cx + 6, cy + 5);
        ctx.lineTo(cx - 6, cy + 5);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else if (typeId.includes("cargo")) {
        // Square with center cross
        ctx.beginPath();
        ctx.rect(cx - 6, cy - 6, 12, 12);
        ctx.fill();
        ctx.stroke();
        ctx.strokeStyle = "#101215";
        ctx.beginPath();
        ctx.moveTo(cx - 4, cy);
        ctx.lineTo(cx + 4, cy);
        ctx.moveTo(cx, cy - 4);
        ctx.lineTo(cx, cy + 4);
        ctx.stroke();
      } else if (typeId.includes("rover")) {
        // Diamond
        ctx.beginPath();
        ctx.moveTo(cx, cy - 7);
        ctx.lineTo(cx + 7, cy);
        ctx.lineTo(cx, cy + 7);
        ctx.lineTo(cx - 7, cy);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else if (typeId.includes("relay")) {
        // Hexagon
        ctx.beginPath();
        for (let a = 0; a < 6; a++) {
          const angle = (a * Math.PI) / 3;
          const hx = cx + 7 * Math.cos(angle);
          const hy = cy + 7 * Math.sin(angle);
          if (a === 0) ctx.moveTo(hx, hy);
          else ctx.lineTo(hx, hy);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        // Base / default square outline
        ctx.strokeRect(cx - 5, cy - 5, 10, 10);
      }

      // 2-character label beside agent
      const lbl = ag.id.slice(0, 2).toUpperCase();
      ctx.fillStyle = "#E8E6E1";
      ctx.font = '10px "IBM Plex Mono"';
      ctx.fillText(lbl, cx + 8, cy + 3);
    });

    // 8. North Arrow & Scale Indicator
    ctx.strokeStyle = "#A9ADB1";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(width - 24, 28);
    ctx.lineTo(width - 24, 12);
    ctx.stroke();
    ctx.fillStyle = "#A9ADB1";
    ctx.font = '10px "IBM Plex Mono"';
    ctx.fillText("N", width - 27, 10);
  }, [gridSize, terrain, plume, beliefHeatmap, agents, detections, radioEdges, selectedAgentId, layers]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * gridSize[0]);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * gridSize[1]);

    if (x >= 0 && x < gridSize[0] && y >= 0 && y < gridSize[1]) {
      const t = terrain[y]?.[x] || "unknown";
      setHoverCell({ x, y, val: t });
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onSelectAgent) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * gridSize[0]);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * gridSize[1]);

    const clicked = Object.values(agents).find(
      (ag) => Math.abs(ag.pos[0] - x) <= 1 && Math.abs(ag.pos[1] - y) <= 1
    );
    onSelectAgent(clicked ? clicked.id : null);
  };

  const handleMouseLeave = () => {
    setHoverCell(null);
  };

  // If 3D is active, render MumbaiMap (MapLibre + deck.gl interleaved)
  if (use3d) {
    return (
      <MumbaiMap
        gridSize={gridSize}
        terrain={terrain}
        plume={plume}
        beliefHeatmap={beliefHeatmap}
        agents={agents}
        detections={detections}
        radioEdges={radioEdges}
        forecast={forecast}
        wind={wind}
        activeEscalation={activeEscalation}
        escalationTarget={escalationTarget}
        selectedAgentId={selectedAgentId}
        onSelectAgent={onSelectAgent}
        onToggle2D={() => setUse3d(false)}
        onInjectEvent={onInjectEvent}
        onNoFlyPolygon={onNoFlyPolygon}
        onTaskOverride={onTaskOverride}
        focusTargetCell={focusTargetCell}
        previewPlanRoutes={previewPlanRoutes}
      />
    );
  }

  return (
    <div className="relative w-full h-full bg-ground border-r border-rule flex flex-col overflow-hidden select-none">
      <div className="relative flex-1 overflow-hidden">
        <canvas
          ref={canvasRef}
          width={800}
          height={600}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="w-full h-full block cursor-crosshair"
        />

        {/* Hover Readout in Plex Mono */}
        {hoverCell && (
          <div className="absolute top-2 left-2 px-2 py-1 bg-surface border border-rule font-mono text-xs text-ink pointer-events-none">
            [{hoverCell.x}, {hoverCell.y}] · {hoverCell.val}
          </div>
        )}

        {/* Attribution */}
        <div className="absolute bottom-1 left-2 text-[10px] text-ink-3 font-sans pointer-events-none">
          © OpenStreetMap contributors (ODbL)
        </div>
      </div>

      {/* Layer Toggles Along Bottom Edge */}
      <div className="h-7 border-t border-rule bg-surface px-3 flex items-center justify-between text-xs font-mono">
        <div className="flex items-center space-x-4">
          <span className="text-ink-3 text-[11px]">Layers:</span>
          <button
            type="button"
            onClick={() => toggleLayer("belief")}
            className={`hover:text-ink ${layers.belief ? "underline font-medium text-ink" : "text-ink-3"}`}
          >
            Belief
          </button>
          <button
            type="button"
            onClick={() => toggleLayer("plume")}
            className={`hover:text-ink ${layers.plume ? "underline font-medium text-ink" : "text-ink-3"}`}
          >
            Plume
          </button>
          <button
            type="button"
            onClick={() => toggleLayer("radio")}
            className={`hover:text-ink ${layers.radio ? "underline font-medium text-ink" : "text-ink-3"}`}
          >
            Radio
          </button>
          <button
            type="button"
            onClick={() => toggleLayer("routes")}
            className={`hover:text-ink ${layers.routes ? "underline font-medium text-ink" : "text-ink-3"}`}
          >
            Routes
          </button>
        </div>

        <button
          type="button"
          onClick={() => setUse3d(true)}
          className="px-2 py-0.5 border border-rule hover:border-attention text-ink hover:text-attention bg-surface-raised font-mono text-[11px]"
        >
          3D deck
        </button>
      </div>
    </div>
  );
};
