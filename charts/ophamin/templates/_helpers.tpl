{{/* vim: set filetype=mustache: */}}

{{/*
Expand the name of the chart.
*/}}
{{- define "ophamin.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
Respects user-supplied .Values.fullnameOverride if present.
*/}}
{{- define "ophamin.fullname" -}}
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

{{/*
Chart label — appears in metadata.labels for every resource.
*/}}
{{- define "ophamin.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels — applied to every k8s object the chart creates.
*/}}
{{- define "ophamin.labels" -}}
helm.sh/chart: {{ include "ophamin.chart" . }}
{{ include "ophamin.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels — narrower subset for Deployment.spec.selector + Service.spec.selector.
NOTE: NEVER change these labels after initial release — Kubernetes Deployment
selectors are immutable.
*/}}
{{- define "ophamin.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ophamin.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Component-specific selector labels — for HTTP vs MCP pod differentiation.
*/}}
{{- define "ophamin.httpSelectorLabels" -}}
{{ include "ophamin.selectorLabels" . }}
app.kubernetes.io/component: http-serve
{{- end -}}

{{- define "ophamin.mcpSelectorLabels" -}}
{{ include "ophamin.selectorLabels" . }}
app.kubernetes.io/component: mcp-serve
{{- end -}}

{{/*
ServiceAccount name — uses the override if set, otherwise the chart fullname.
*/}}
{{- define "ophamin.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ophamin.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Image reference — combines repository + tag, with chart appVersion as
fallback when values.image.tag is empty.
*/}}
{{- define "ophamin.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}
