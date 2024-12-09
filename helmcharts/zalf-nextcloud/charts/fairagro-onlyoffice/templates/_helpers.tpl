{{/*
Expand the name of the chart.
*/}}
{{- define "fairagro-onlyoffice.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fairagro-onlyoffice.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "fairagro-onlyoffice.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fairagro-onlyoffice.labels" -}}
helm.sh/chart: {{ include "fairagro-onlyoffice.chart" . }}
{{ include "fairagro-onlyoffice.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fairagro-onlyoffice.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fairagro-onlyoffice.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fairagro-onlyoffice.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "fairagro-onlyoffice.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
The database credentials secret name
*/}}
{{- define "fairagro-onlyoffice.database_secret" -}}
{{- printf "%s.%s.credentials.postgresql.acid.zalan.do" .Values.postgres.username (include "fairagro-onlyoffice.databasename" .) }}
{{- end }}

{{/*
The onlyoffice jwt token secret name
*/}}
{{- define "fairagro-onlyoffice.jwt_secret" -}}
{{- printf "%s-%s" (include "fairagro-onlyoffice.fullname" .) "jwt-secret" }}
{{- end }}

{{/*
The onlyoffice licence secret name
*/}}
{{- define "fairagro-onlyoffice.licence" -}}
{{- printf "%s-%s" (include "fairagro-onlyoffice.fullname" .) "licence" }}
{{- end }}

{{/*
The full image name including version tag or digest
*/}}
{{- define "fairagro-onlyoffice.imagename" -}}
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
The name of the database object
*/}}
{{- define "fairagro-onlyoffice.databasename" -}}
{{- printf "%s-%s" (include "fairagro-onlyoffice.fullname" .) "postgresql" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
The name of the configuration object
*/}}
{{- define "fairagro-onlyoffice.config" -}}
{{- printf "%s-%s" (include "fairagro-onlyoffice.fullname" .) "config" }}
{{- end }}