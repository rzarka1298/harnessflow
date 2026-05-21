// Parse the workflow YAML into a tiny graph shape the DAG viewer can render.
// Keeps the parse client-side; the API doesn't yet return a parsed IR.
import { parse } from "yaml";

export interface StepNode {
  name: string;
  type: string;
  after: string[];
}

export function parseWorkflowGraph(yamlSource: string): StepNode[] {
  try {
    const doc = parse(yamlSource) as
      | {
          steps?: Record<string, { type?: string; after?: string[] }>;
        }
      | null;
    if (!doc?.steps) return [];
    return Object.entries(doc.steps).map(([name, step]) => ({
      name,
      type: step?.type ?? "(unknown)",
      after: Array.isArray(step?.after) ? step.after : [],
    }));
  } catch {
    return [];
  }
}
