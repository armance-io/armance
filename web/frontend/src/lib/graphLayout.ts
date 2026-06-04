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

export function packLanes(nodes: RawNode[]): Record<string, number> {
  const lanes: Record<string, number> = {};
  const laneEndTimes: number[] = [];

  // Sort nodes by started_at if available
  const sorted = [...nodes].sort((a, b) => {
    const startAStr = a.data.started_at as string | undefined;
    const startBStr = b.data.started_at as string | undefined;
    const startA = startAStr ? new Date(startAStr).getTime() : 0;
    const startB = startBStr ? new Date(startBStr).getTime() : 0;
    return startA - startB;
  });

  for (const n of sorted) {
    const startedStr = n.data.started_at as string | undefined;
    const endedStr = n.data.ended_at as string | undefined;
    const started = startedStr ? new Date(startedStr).getTime() : null;
    const ended = endedStr ? new Date(endedStr).getTime() : null;

    if (started === null || ended === null) {
      // For queued, working or unstarted nodes, place in lane 0 by default
      lanes[n.id] = 0;
      continue;
    }

    // Find the first lane where this node doesn't overlap
    let assignedLane = 0;
    while (assignedLane < laneEndTimes.length) {
      const lastEnded = laneEndTimes[assignedLane] ?? 0;
      // If the last node in this lane ended before or at the time this one started, we can use it!
      if (lastEnded <= started) {
        break;
      }
      assignedLane++;
    }

    lanes[n.id] = assignedLane;
    laneEndTimes[assignedLane] = ended;
  }

  return lanes;
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

  // Compute parallel lanes if there are overlapping times (D.11)
  const nodeLanes = packLanes(rawNodes);

  const nodes = rawNodes.map((n) => {
    const pos = g.node(n.id);
    const lane = nodeLanes[n.id] || 0;
    const yOffset = lane * 120; // 120px spacing between concurrent lanes

    return {
      id: n.id,
      type: "stepNode",
      data: n.data,
      position: {
        x: pos.x - NODE_W / 2,
        y: (pos.y - NODE_H / 2) + yOffset,
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
