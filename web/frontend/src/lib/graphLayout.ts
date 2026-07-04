import dagre from "@dagrejs/dagre";
import type { StepNodeData } from "@/components/workflow/StepNode";

const NODE_W = 200;
const NODE_H = 72;

export interface RawNode {
  id: string;
  data: StepNodeData;
}

export interface RawEdge {
  id: string;
  source: string;
  target: string;
}

export function computeLayout(
  rawNodes: RawNode[],
  rawEdges: RawEdge[],
  _options?: unknown,
): {
  nodes: Array<{
    id: string;
    type: string;
    data: StepNodeData;
    position: { x: number; y: number };
  }>;
  edges: RawEdge[];
} {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 80 });

  rawNodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  });
  rawEdges.forEach((e) => {
    g.setEdge(e.source, e.target);
  });

  dagre.layout(g);

  // Dagre alone owns the positions. A previous "parallel lanes" pass added
  // a time-based y-offset ON TOP of dagre's layout, which made same-rank
  // nodes overlap as soon as a live run supplied started_at/ended_at.
  const nodes = rawNodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: "stepNode",
      data: n.data,
      position: {
        x: pos.x - NODE_W / 2,
        y: pos.y - NODE_H / 2,
      },
    };
  });

  const edges = rawEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
  }));

  return { nodes, edges };
}
