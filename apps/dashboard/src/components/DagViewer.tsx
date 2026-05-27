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

// Mirrors harnessflow.run.v1.StepStatus enum values. Kept in sync with the
// protos by hand; the dashboard already does this in /runs and /runs/[id].
const STATUS_PENDING = 1;
const STATUS_RUNNING = 2;
const STATUS_COMPLETED = 3;
const STATUS_FAILED = 4;
const STATUS_SKIPPED = 5;

/**
 * Lays out a workflow's parsed steps left-to-right via dagre and renders the
 * resulting DAG with @xyflow/react.
 *
 * - Without `stepStatuses`: definition view (used by `/workflows/[id]`).
 *   Nodes are bordered by step type, no animation.
 * - With `stepStatuses`: live run-state view (used by `/runs/[id]`).
 *   Each node is colored by its current `StepStatus` and the in-progress
 *   step pulses, edges entering the running step animate, edges that have
 *   already fired are solid green. Re-rendering on every 2s poll is what
 *   produces the live update.
 */
export function DagViewer({
  steps,
  stepStatuses,
}: {
  steps: StepNode[];
  stepStatuses?: Record<string, number>;
}) {
  const { nodes, edges } = useMemo(
    () => layout(steps, stepStatuses),
    [steps, stepStatuses],
  );

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

function layout(
  steps: StepNode[],
  stepStatuses: Record<string, number> | undefined,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const s of steps) g.setNode(s.name, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const s of steps) for (const dep of s.after) g.setEdge(dep, s.name);
  dagre.layout(g);

  const nodes: Node[] = steps.map((s) => {
    const n = g.node(s.name);
    const status = stepStatuses?.[s.name];
    return {
      id: s.name,
      data: { label: stepLabel(s, status) },
      position: { x: n.x - NODE_WIDTH / 2, y: n.y - NODE_HEIGHT / 2 },
      style: nodeStyle(s.type, status),
      // Wrapper-level className — Tailwind's animate-pulse rides here so
      // the whole node pulses while its step is running.
      className: status === STATUS_RUNNING ? "animate-pulse" : undefined,
    };
  });
  const edges: Edge[] = steps.flatMap((s) =>
    s.after.map((from) => {
      const fromStatus = stepStatuses?.[from];
      const toStatus = stepStatuses?.[s.name];
      // An edge is "active" (xyflow's flowing-dashes animation) when its
      // source has completed and its target is currently running — that's
      // the work-in-flight wave.
      const isActive =
        fromStatus === STATUS_COMPLETED && toStatus === STATUS_RUNNING;
      // An edge is "fired" once its source has completed; colored solid
      // green so finished branches read as done.
      const isFired = fromStatus === STATUS_COMPLETED && toStatus !== undefined;
      return {
        id: `${from}->${s.name}`,
        source: from,
        target: s.name,
        animated: isActive,
        style: isFired ? { stroke: "#10b981", strokeWidth: 2 } : undefined,
      };
    }),
  );
  return { nodes, edges };
}

function stepLabel(s: StepNode, status: number | undefined) {
  // The status icon sits to the right of the name so the eye still parses
  // "<name> · <type>" left-to-right.
  const icon = statusIcon(status);
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1.5 text-sm font-medium">
        <span>{s.name}</span>
        {icon && <span aria-hidden>{icon}</span>}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{s.type}</div>
    </div>
  );
}

function statusIcon(status: number | undefined): string | null {
  switch (status) {
    case STATUS_COMPLETED:
      return "✓";
    case STATUS_FAILED:
      return "✗";
    case STATUS_SKIPPED:
      return "↷";
    default:
      return null;
  }
}

// Type-driven palette for the definition view. Also reused as a left-stripe
// accent on completed nodes in the run-state view so the visual still hints
// at what kind of step it was once things settle.
const TYPE_PALETTE: Record<string, string> = {
  llm_call: "#3b82f6", // blue
  retrieve: "#10b981", // green
  tool_call: "#f59e0b", // amber
  verify: "#a855f7", // purple
};

function nodeStyle(
  type: string,
  status: number | undefined,
): React.CSSProperties {
  // No status → definition view, keep the existing type-based palette.
  if (status === undefined) {
    const color = TYPE_PALETTE[type] ?? "#6b7280";
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
  const typeColor = TYPE_PALETTE[type] ?? "#6b7280";
  switch (status) {
    case STATUS_RUNNING:
      return {
        background: "#dbeafe", // blue-100
        borderColor: "#3b82f6",
        borderWidth: 2,
        borderStyle: "solid",
        borderRadius: 8,
        padding: 8,
        width: NODE_WIDTH,
      };
    case STATUS_COMPLETED:
      return {
        background: "#dcfce7", // green-100
        borderColor: "#10b981",
        borderWidth: 2,
        borderStyle: "solid",
        borderRadius: 8,
        padding: 8,
        width: NODE_WIDTH,
        borderLeftColor: typeColor,
        borderLeftWidth: 6,
      };
    case STATUS_FAILED:
      return {
        background: "#fee2e2", // red-100
        borderColor: "#ef4444",
        borderWidth: 2,
        borderStyle: "solid",
        borderRadius: 8,
        padding: 8,
        width: NODE_WIDTH,
      };
    case STATUS_SKIPPED:
      return {
        background: "#f3f4f6", // gray-100
        borderColor: "#9ca3af",
        borderWidth: 2,
        borderStyle: "dashed",
        borderRadius: 8,
        padding: 8,
        width: NODE_WIDTH,
        opacity: 0.7,
      };
    case STATUS_PENDING:
    default:
      return {
        background: "white",
        borderColor: "#d1d5db", // gray-300
        borderWidth: 2,
        borderStyle: "dashed",
        borderRadius: 8,
        padding: 8,
        width: NODE_WIDTH,
        opacity: 0.55,
      };
  }
}
