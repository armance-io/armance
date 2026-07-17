import {
  type CSSProperties,
  type FC,
  useCallback,
  useMemo,
} from "react";
import {
  ReactFlow,
  type Node,
  type Edge,
  type NodeTypes,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { StepNode } from "@/components/workflow/StepNode";
import { computeLayout } from "@/lib/graphLayout";

/* ─── Types ──────────────────────────────────────────────────────────────── */

import type { StepNodeData } from "@/components/workflow/StepNode";

export interface WorkflowGraphProps {
  nodes: Array<{ id: string; data: StepNodeData }>;
  edges: Array<{ id: string; source: string; target: string }>;
  onNodeClick?: (id: string) => void;
  className?: string;
  t: (key: string) => string;
}

function layoutNodes(
  rawNodes: Array<{ id: string; data: StepNodeData }>,
  rawEdges: Array<{ id: string; source: string; target: string }>,
  t: (key: string) => string,
): { nodes: Node[]; edges: Edge[] } {
  const result = computeLayout(rawNodes, rawEdges);

  const nodes: Node[] = result.nodes.map((n) => ({
    ...n,
    // Inject the translator so StepNode can render an i18n'd stage badge.
    data: { ...n.data, t } as StepNodeData,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }));

  const edges: Edge[] = result.edges.map((e) => ({
    ...e,
    // smoothstep routes around nodes; "straight" cut THROUGH other nodes
    // on fan-ins (a step with 4 upstream deps looked like spaghetti).
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10 },
    style: {
      stroke: "var(--rule, #d6c8ad)",
      strokeWidth: 1,
    },
  }));

  return { nodes, edges };
}

/* ─── Creuset lane backdrop ──────────────────────────────────────────────── */

const NODE_W = 200;
const NODE_H = 72;
const ZONE_PAD = 16;
// Two crucible clusters are considered distinct when a horizontal gap wider
// than one node column separates them (a plain `standard` step in between).
const CLUSTER_GAP = NODE_W + 120;

export interface CrucibleZone {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Bounding rectangles behind each contiguous crucible sub-graph. Robust and
 * layout-agnostic: it reads laid-out node positions + `data.stage`, clusters
 * the non-`standard` nodes by X proximity, and boxes each cluster. Returns
 * an empty list when a run has no crucible (the common legacy case).
 */
export function computeCrucibleZones(nodes: Node[]): CrucibleZone[] {
  const staged = nodes
    .filter((n) => {
      const s = (n.data as StepNodeData)?.stage;
      return s && s !== "standard";
    })
    .map((n) => ({ x: n.position.x, y: n.position.y }))
    .sort((a, b) => a.x - b.x);

  if (staged.length === 0) return [];

  const clusters: Array<typeof staged> = [];
  let current: typeof staged = [];
  let lastX = -Infinity;
  for (const p of staged) {
    if (current.length > 0 && p.x - lastX > CLUSTER_GAP) {
      clusters.push(current);
      current = [];
    }
    current.push(p);
    lastX = p.x;
  }
  if (current.length > 0) clusters.push(current);

  return clusters.map((cluster, i) => {
    const minX = Math.min(...cluster.map((p) => p.x));
    const maxX = Math.max(...cluster.map((p) => p.x));
    const minY = Math.min(...cluster.map((p) => p.y));
    const maxY = Math.max(...cluster.map((p) => p.y));
    return {
      id: `crucible-${i}`,
      x: minX - ZONE_PAD,
      y: minY - ZONE_PAD,
      w: maxX - minX + NODE_W + ZONE_PAD * 2,
      h: maxY - minY + NODE_H + ZONE_PAD * 2,
    };
  });
}

function zoneNodes(zones: CrucibleZone[]): Node[] {
  return zones.map((z) => ({
    id: z.id,
    type: "crucibleZone",
    position: { x: z.x, y: z.y },
    data: { w: z.w, h: z.h },
    draggable: false,
    selectable: false,
    focusable: false,
    zIndex: -1,
    style: { zIndex: -1 },
  }));
}

/* ─── Custom node types ──────────────────────────────────────────────────── */

const nodeTypes: NodeTypes = {
  stepNode: ({ data, selected }: { data: StepNodeData; selected?: boolean }) => (
    <StepNode data={data} selected={selected} />
  ),
  crucibleZone: ({ data }: { data: { w: number; h: number } }) => (
    <div
      data-testid="crucible-zone"
      aria-hidden="true"
      style={{
        width: data.w,
        height: data.h,
        borderRadius: "2px",
        background:
          "color-mix(in srgb, var(--accent-soft, #b7a4c9) 16%, transparent)",
        border: "1px solid color-mix(in srgb, var(--accent-soft, #b7a4c9) 55%, transparent)",
        pointerEvents: "none",
        boxSizing: "border-box",
      }}
    />
  ),
};

/* ─── Component ──────────────────────────────────────────────────────────── */

export const WorkflowGraph: FC<WorkflowGraphProps> = ({
  nodes: rawNodes,
  edges: rawEdges,
  onNodeClick,
  className,
  t,
}) => {
  const { nodes, edges } = useMemo(
    () => layoutNodes(rawNodes, rawEdges, t),
    [rawNodes, rawEdges, t],
  );

  // Creuset lane backdrop: soft `--accent-soft` rectangles behind each
  // contiguous crucible sub-graph (draft/critique/synthesis/gate), so the
  // parallel drafts → single verdict pipeline reads as one movement.
  const crucibleZones = useMemo(() => computeCrucibleZones(nodes), [nodes]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  const isEmpty = rawNodes.length === 0;

  const rootStyle: CSSProperties = {
    width: "100%",
    height: "100%",
    minHeight: "320px",
    background: "var(--bg-paper-deep, #e8dfcd)",
    position: "relative",
    backgroundImage:
      "radial-gradient(circle, var(--rule, #d6c8ad) 0.5px, transparent 0.5px)",
    backgroundSize: "20px 20px",
    backgroundPosition: "0 0",
  };

  /* Reduce dot grid opacity */
  const overlayStyle: CSSProperties = {
    position: "absolute",
    inset: 0,
    background: "color-mix(in srgb, var(--bg-paper-deep, #e8dfcd) 94%, transparent)",
    pointerEvents: "none",
    zIndex: 0,
  };

  const emptyStyle: CSSProperties = {
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "12px",
    zIndex: 1,
  };

  const emptyFleuronStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "36px",
    color: "var(--accent, #6b4f8a)",
    lineHeight: 1,
  };

  const emptyTextStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "16px",
    color: "var(--ink-faint, #9c8e7e)",
  };

  if (isEmpty) {
    return (
      <div style={rootStyle} className={className}>
        <div style={overlayStyle} />
        <div style={emptyStyle}>
          <span style={emptyFleuronStyle} aria-hidden="true">
            ❦
          </span>
          <span style={emptyTextStyle}>
            {t("workflow:graph.empty")}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div style={rootStyle} className={className}>
      <style>{`
        .react-flow__handle { opacity: 0 !important; width: 1px !important; height: 1px !important; }
        .react-flow__controls, .react-flow__minimap { display: none !important; }
        .react-flow__node.react-flow__node-stepNode:hover { outline: 1px solid var(--accent, #6b4f8a); }
        .react-flow__node-crucibleZone { pointer-events: none; }
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>
      <div style={overlayStyle} />
      <ReactFlow
        nodes={[...zoneNodes(crucibleZones), ...nodes]}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        panOnScroll
        fitView
        proOptions={{ hideAttribution: true }}
        style={{ zIndex: 1 }}
      />
    </div>
  );
};

export default WorkflowGraph;
