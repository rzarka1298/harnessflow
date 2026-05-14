# ADR-0002: Use Connect-Go over raw gRPC for the API surface

Date: 2026-05-14
Status: Accepted

## Context

The Go orchestrator (`apps/api`) needs to expose RPCs callable from (a) a browser-based Next.js dashboard, (b) a Python eval-runner client, (c) potentially external SDKs in the future. The natural choice given the Go + proto stack is gRPC — but gRPC doesn't work in browsers without a proxy (envoy or grpc-web).

Connect (`connectrpc.com/connect`) is a 2023+ protocol layer from Buf that speaks gRPC, gRPC-Web, and its own Connect HTTP/JSON protocol from one server, with one set of generated types.

## Decision

Use **Connect-Go** (`connectrpc.com/connect`) for all RPC services. Use **Buf** for code generation. Generate clients for Go (server-side tests, eval runner), Python (workers and tools), and TypeScript (dashboard via Connect-ES).

## Consequences

- **Enables:** the dashboard calls the same services as any backend client, with no envoy/grpc-web sidecar. One `.proto` file is the source of truth across three languages. cURL works against the service (Connect's HTTP/JSON mode), which speeds debugging.
- **Forecloses:** some gRPC ecosystem tooling assumes raw gRPC and may not work (e.g., grpcurl on the Connect HTTP endpoint requires `--proto`-mode flags). Acceptable.
- **Operational:** Buf codegen is run via `make proto`. Generated code is committed to `packages/sdk/gen/` so cloners don't need codegen tools.
- **Recruiter signal:** Connect is the modern choice. Using raw `grpc-go` + `grpc-gateway` in 2026 reads as someone who learned the stack in 2020.

## Alternatives considered

- **Raw gRPC (`google.golang.org/grpc`) + grpc-gateway.** Rejected: more moving parts, dashboard needs envoy.
- **REST + OpenAPI (no proto).** Rejected: gives up type safety across the three languages; we want one source of truth.
- **GraphQL.** Rejected: dashboard is a small, well-typed surface, not a flexible-query app.
- **tRPC.** Rejected: TS-only, doesn't extend to Go server.
