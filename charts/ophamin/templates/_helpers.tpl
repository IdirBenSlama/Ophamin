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

{{/*
ServiceAccount annotations — merges user-supplied
.Values.serviceAccount.annotations with the cloud-managed workload-identity
annotation when one of the workloadIdentity.{gke,eks,aks} blocks is
enabled. Mutually exclusive: enabling multiple clouds raises a fatal
template error so the misconfiguration is caught at install time.
*/}}
{{- define "ophamin.serviceAccount.annotations" -}}
{{- $wi := .Values.workloadIdentity | default dict -}}
{{- $gke := and $wi.gke $wi.gke.enabled -}}
{{- $eks := and $wi.eks $wi.eks.enabled -}}
{{- $aks := and $wi.aks $wi.aks.enabled -}}
{{- $enabled := 0 -}}
{{- if $gke }}{{- $enabled = add $enabled 1 -}}{{- end -}}
{{- if $eks }}{{- $enabled = add $enabled 1 -}}{{- end -}}
{{- if $aks }}{{- $enabled = add $enabled 1 -}}{{- end -}}
{{- if gt $enabled 1 -}}
{{- fail "workloadIdentity: only one of gke / eks / aks may be enabled at once" -}}
{{- end -}}
{{- $merged := dict -}}
{{- with .Values.serviceAccount.annotations -}}
  {{- range $k, $v := . -}}
    {{- $_ := set $merged $k $v -}}
  {{- end -}}
{{- end -}}
{{- if $gke -}}
  {{- if not $wi.gke.gcpServiceAccount -}}
    {{- fail "workloadIdentity.gke.enabled=true requires workloadIdentity.gke.gcpServiceAccount" -}}
  {{- end -}}
  {{- $_ := set $merged "iam.gke.io/gcp-service-account" $wi.gke.gcpServiceAccount -}}
{{- end -}}
{{- if $eks -}}
  {{- if not $wi.eks.roleArn -}}
    {{- fail "workloadIdentity.eks.enabled=true requires workloadIdentity.eks.roleArn" -}}
  {{- end -}}
  {{- $_ := set $merged "eks.amazonaws.com/role-arn" $wi.eks.roleArn -}}
{{- end -}}
{{- if $aks -}}
  {{- if not $wi.aks.clientId -}}
    {{- fail "workloadIdentity.aks.enabled=true requires workloadIdentity.aks.clientId" -}}
  {{- end -}}
  {{- $_ := set $merged "azure.workload.identity/client-id" $wi.aks.clientId -}}
  {{- with $wi.aks.tenantId -}}
    {{- $_ := set $merged "azure.workload.identity/tenant-id" . -}}
  {{- end -}}
{{- end -}}
{{- if $merged -}}
{{ toYaml $merged }}
{{- end -}}
{{- end -}}

{{/*
AKS workload-identity Pod label injection — AKS requires the
`azure.workload.identity/use=true` label on the Pod template (not just
the SA annotation). Returns "true" when AKS workload-identity is
enabled, empty otherwise. Callers nest under `metadata.labels` next to
their user-supplied podLabels.
*/}}
{{- define "ophamin.aksPodLabelEnabled" -}}
{{- $wi := .Values.workloadIdentity | default dict -}}
{{- if and $wi.aks $wi.aks.enabled -}}true{{- end -}}
{{- end -}}
