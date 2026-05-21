"use client";

import { useMemo } from "react";
import dagre from "dagre";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { StepNode } from "@/lib/yaml-graph";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;

/**
 * Lays out a workflow's parsed steps left-to-right via dagre and renders the
 * resulting DAG with @xyflow/react. Pure presentation — no live run state yet
 * (animated state lands in Week 9).
 */
export function DagViewer({ steps }: { steps: StepNode[] }) {
  const { nodes, edges } = useMemo(() => layout(steps), [steps]);

  if (steps.length === 0) {
    return (
      <div className="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
        (no steps to render)
      </div>
    );
  }

  return (
    <div className="h-[400px] w-full rounded border border-gray-200 dark:border-gray-800">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false}>
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
      </ReactFlow>
    </div>
  );
}

function layout(steps: StepNode[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const s of steps) g.setNode(s.name, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const s of steps) for (const dep of s.after) g.setEdge(dep, s.name);
  dagre.layout(g);

  const nodes: Node[] = steps.map((s) => {
    const n = g.node(s.name);
    return {
      id: s.name,
      data: { label: stepLabel(s) },
      position: { x: n.x - NODE_WIDTH / 2, y: n.y - NODE_HEIGHT / 2 },
      style: nodeStyle(s.type),
    };
  });
  const edges: Edge[] = steps.flatMap((s) =>
    s.after.map((from) => ({
      id: `${from}->${s.name}`,
      source: from,
      target: s.name,
      animated: false,
    })),
  );
  return { nodes, edges };
}

function stepLabel(s: StepNode) {
  return (
    <div className="text-center">
      <div className="text-sm font-medium">{s.name}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{s.type}</div>
    </div>
  );
}

function nodeStyle(type: string): React.CSSProperties {
  const palette: Record<string, string> = {
    llm_call: "#3b82f6", // blue
    retrieve: "#10b981", // green
    tool_call: "#f59e0b", // amber
    verify: "#a855f7", // purple
  };
  const color = palette[type] ?? "#6b7280";
  return {
    background: "white",
    borderColor: color,
    borderWidth: 2,
    borderStyle: "solid",
    borderRadius: 8,
    padding: 8,
    width: NODE_WIDTH,
  };
}
