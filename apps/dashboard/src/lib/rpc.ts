// Connect-Web client + service-handle helpers.
//
// The generated TypeScript code at packages/sdk/gen/ts uses protobuf-es v2,
// which exposes service *descriptors* as values that you pass into
// `createClient` from @connectrpc/connect. There is no separate Connect-ES
// codegen step.
import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";

import { WorkflowService } from "@/gen/workflow/v1/workflow_pb";
import { RunService } from "@/gen/run/v1/run_pb";
import { EvalService } from "@/gen/eval/v1/eval_pb";

// The dashboard runs on http://localhost:3000 by default (Next dev server)
// while the API listens on 8080. Override via NEXT_PUBLIC_API_BASE_URL for
// deployed environments.
const baseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

const transport = createConnectTransport({
  baseUrl,
  // Use the Connect protocol with JSON encoding so requests are inspectable
  // in the browser devtools network panel.
  useBinaryFormat: false,
});

export const workflowClient = createClient(WorkflowService, transport);
export const runClient = createClient(RunService, transport);
export const evalClient = createClient(EvalService, transport);
