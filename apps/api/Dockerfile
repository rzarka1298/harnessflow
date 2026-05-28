# syntax=docker/dockerfile:1
# Multi-stage build for the HarnessFlow Go orchestrator.
#
# IMPORTANT: the build context is the REPO ROOT, not apps/api. The api
# module depends on packages/sdk/gen/go via the workspace (go.work), and
# that module has no published version — so go.work + both member modules
# must all be present in the build. Build with:
#
#   docker build -f apps/api/Dockerfile -t harnessflow/api .
#
# (The Makefile `kind-load` target does exactly this.)

FROM golang:1.26-alpine AS build
WORKDIR /src
# Workspace file + both modules' manifests first so `go mod download`
# caches independently of source changes.
COPY go.work ./
COPY apps/api/go.mod apps/api/go.sum ./apps/api/
COPY packages/sdk/gen/go/go.mod ./packages/sdk/gen/go/
RUN go mod download -x
# Sources for both workspace members.
COPY apps/api ./apps/api
COPY packages/sdk/gen/go ./packages/sdk/gen/go
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./apps/api/cmd/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/api /api
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/api"]
