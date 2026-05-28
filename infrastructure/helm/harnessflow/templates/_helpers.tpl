{{/* Common name helpers — standard helm-create boilerplate adapted for
     our naming. Every first-party resource uses the chart name as a
     prefix so a single install can coexist with another namespace's. */}}

{{- define "harnessflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "harnessflow.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels — apply to every resource so kubectl get can filter
     by `app.kubernetes.io/name=harnessflow` and Helm can adopt the
     resources on upgrade. */}}
{{- define "harnessflow.labels" -}}
helm.sh/chart: {{ include "harnessflow.chart" . }}
{{ include "harnessflow.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "harnessflow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "harnessflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Per-component name + selector. Pass the component as a 1-arg dict:
     {{ include "harnessflow.componentName" (dict "ctx" . "component" "api") }} */}}
{{- define "harnessflow.componentName" -}}
{{- printf "%s-%s" (include "harnessflow.fullname" .ctx) .component | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "harnessflow.componentLabels" -}}
{{ include "harnessflow.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "harnessflow.componentSelectorLabels" -}}
{{ include "harnessflow.selectorLabels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Image reference: per-service repository (joined to images.registry)
     + per-service tag (falling back to the shared images.tag). Returns
     a fully-qualified image string. */}}
{{- define "harnessflow.image" -}}
{{- $registry := .ctx.Values.images.registry -}}
{{- $tag := default .ctx.Values.images.tag .svc.image.tag -}}
{{- printf "%s/%s:%s" $registry .svc.image.repository $tag -}}
{{- end -}}

{{/* Postgres connection bits. Uses the bundled first-party Postgres
     (templates/postgres.yaml) when enabled, otherwise the externalPostgres
     block. The password always lives in a Secret under the key
     `postgres-password` (bundled or external), wired via secretKeyRef. */}}
{{- define "harnessflow.postgresHost" -}}
{{- if .Values.postgresql.enabled -}}
{{- include "harnessflow.componentName" (dict "ctx" . "component" "postgres") -}}
{{- else -}}
{{- required "externalPostgres.host is required when postgresql.enabled=false" .Values.externalPostgres.host -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.postgresPort" -}}
{{- if .Values.postgresql.enabled -}}
5432
{{- else -}}
{{- .Values.externalPostgres.port | default 5432 -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.postgresDatabase" -}}
{{- if .Values.postgresql.enabled -}}
{{- .Values.postgresql.auth.database -}}
{{- else -}}
{{- .Values.externalPostgres.database -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.postgresUser" -}}
{{- if .Values.postgresql.enabled -}}
{{- .Values.postgresql.auth.username -}}
{{- else -}}
{{- .Values.externalPostgres.user -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.postgresSecretName" -}}
{{- if .Values.postgresql.enabled -}}
{{- include "harnessflow.componentName" (dict "ctx" . "component" "postgres") -}}
{{- else -}}
{{- required "externalPostgres.existingSecret is required when postgresql.enabled=false" .Values.externalPostgres.existingSecret -}}
{{- end -}}
{{- end -}}

{{/* Temporal host. Bundled Temporal subchart names its frontend service
     `<release>-temporal-frontend`. */}}
{{- define "harnessflow.temporalHost" -}}
{{- if .Values.temporal.enabled -}}
{{- printf "%s-temporal-frontend" .Release.Name -}}
{{- else -}}
{{- required "externalTemporal.host is required when temporal.enabled=false" .Values.externalTemporal.host -}}
{{- end -}}
{{- end -}}

{{- define "harnessflow.temporalPort" -}}
{{- if .Values.temporal.enabled -}}
7233
{{- else -}}
{{- .Values.externalTemporal.port | default 7233 -}}
{{- end -}}
{{- end -}}

{{/* LLM-keys secret name. Either we create one (env.keys.create) or
     reference an existing one (env.keys.existing); both can be empty,
     in which case the worker falls back to MockProvider with no env
     wired in. */}}
{{- define "harnessflow.llmKeysSecretName" -}}
{{- if .Values.env.keys.existing -}}
{{- .Values.env.keys.existing -}}
{{- else if .Values.env.keys.create -}}
{{- printf "%s-llm-keys" (include "harnessflow.fullname" .) -}}
{{- end -}}
{{- end -}}
