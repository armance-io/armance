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
): { nodes: Node[]; edges: Edge[] } {
  const result = computeLayout(rawNodes, rawEdges);
  
  const nodes: Node[] = result.nodes.map((n) => ({
    ...n,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }));

  const edges: Edge[] = result.edges.map((e) => ({
    ...e,
    type: "straight",
    markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10 },
    style: {
      stroke: "var(--rule, #d6c8ad)",
      strokeWidth: 1,
    },
  }));

  return { nodes, edges };
}

/* ─── Custom node types ──────────────────────────────────────────────────── */

const nodeTypes: NodeTypes = {
  stepNode: ({ data, selected }: { data: StepNodeData; selected?: boolean }) => (
    <StepNode data={data} selected={selected} />
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
    () => layoutNodes(rawNodes, rawEdges),
    [rawNodes, rawEdges],
  );

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
        .react-flow__node:hover { outline: 1px solid var(--accent, #6b4f8a); }
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>
      <div style={overlayStyle} />
      <ReactFlow
        nodes={nodes}
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
