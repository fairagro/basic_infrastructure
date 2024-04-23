{{/*
Expand the name of the chart.
*/}}
{{- define "zalf-onlyoffice.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "zalf-onlyoffice.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
The full image name including version tag or digest
*/}}
{{- define "zalf-onlyoffice.imagename" -}}
{{- $repositoryName := .Values.image.repository -}}
{{- $separator := ":" -}}
{{- $termination := .Values.image.tag | default .Chart.AppVersion | toString -}}
{{- if .Values.image.digest }}
    {{- $separator = "@" -}}
    {{- $termination = .Values.image.digest | toString -}}
{{- end -}}
{{- printf "%s%s%s"  $repositoryName $separator $termination -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "zalf-onlyoffice.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "zalf-onlyoffice.labels" -}}
helm.sh/chart: {{ include "zalf-onlyoffice.chart" . }}
{{ include "zalf-onlyoffice.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "zalf-onlyoffice.selectorLabels" -}}
app.kubernetes.io/name: {{ include "zalf-onlyoffice.name" . }}
app.kubernetes.io/instance: "{{ .Release.Name }}"
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "zalf-onlyoffice.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "zalf-onlyoffice.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the postgres database
*/}}
{{- define "zalf-onlyoffice.serviceAccountName" -}}
{{- printf "%s-%s" {{ include "zalf-onlyoffice.name" . }} .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}