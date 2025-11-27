{{/*
Expand the name of the chart.
*/}}
{{- define "marty-microservice.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "marty-microservice.fullname" -}}
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
{{- define "marty-microservice.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "marty-microservice.labels" -}}
helm.sh/chart: {{ include "marty-microservice.chart" . }}
{{ include "marty-microservice.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
marty.framework/phase: "phase2"
marty.framework/environment: {{ .Values.environment | default "development" }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "marty-microservice.selectorLabels" -}}
app.kubernetes.io/name: {{ include "marty-microservice.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "marty-microservice.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "marty-microservice.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate database URL
*/}}
{{- define "marty-microservice.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql+asyncpg://%s:%s@%s:%d/%s" .Values.secrets.database.username .Values.secrets.database.password .Values.database.host (.Values.database.port | int) .Values.service.name }}
{{- else }}
{{- printf "postgresql+asyncpg://%s:%s@%s:%d/%s_db" .Values.secrets.database.username .Values.secrets.database.password .Values.database.host (.Values.database.port | int) .Values.service.name }}
{{- end }}
{{- end }}

{{/*
Generate Redis URL
*/}}
{{- define "marty-microservice.redisUrl" -}}
{{- if .Values.secrets.redis.password }}
{{- printf "redis://:%s@%s:6379" .Values.secrets.redis.password (.Values.infrastructure.cache.redis.host | default "redis") }}
{{- else }}
{{- printf "redis://%s:6379" (.Values.infrastructure.cache.redis.host | default "redis") }}
{{- end }}
{{- end }}

{{/*
Generate RabbitMQ URL
*/}}
{{- define "marty-microservice.rabbitmqUrl" -}}
{{- printf "amqp://%s:%s@%s:5672/" .Values.secrets.rabbitmq.username .Values.secrets.rabbitmq.password (.Values.infrastructure.messaging.rabbitmq.host | default "rabbitmq") }}
{{- end }}

{{/*
Default TLS Certificate (for development only)
*/}}
{{- define "defaultTLSCert" -}}
-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAMlyFqk69v+9MA0GCSqGSIb3DQEBBQUAMBQxEjAQBgNVBAMMCWxv
Y2FsaG9zdDAeFw0yANDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBQxEjAQBgNV
BAMMCWxvY2FsaG9zdDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQDTwqq/ynci1kM5
K1L5E7tSzgj0WZ1fgH5h9K5F0v8ZO7X9Z4K5F0v8ZO7X9Z4K5F0v8ZO7X9Z4K5F0
v8ZO7X9ZAgMBAAEwDQYJKoZIhvcNAQEFBQADQQBcH9j6n3A5t8j6n3A5t8j6n3A5
t8j6n3A5t8j6n3A5t8j6n3A5t8j6n3A5t8j6n3A5t8j6n3A5t8j6n3A5
-----END CERTIFICATE-----
{{- end }}

{{/*
Default TLS Private Key (for development only)
*/}}
{{- define "defaultTLSKey" -}}
-----BEGIN PRIVATE KEY-----
MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA08Kqv8p3ItZDOStS
+RO7Us4I9FmdX4B+YfSuRdL/GTu1/WeCuRdL/GTu1/WeCuRdL/GTu1/WeCuRdL/G
Tu1/WQIDAQABAkEAw8Kqv8p3ItZDOStS+RO7Us4I9FmdX4B+YfSuRdL/GTu1/WeC
uRdL/GTu1/WeCuRdL/GTu1/WeCuRdL/GTu1/WQIhAOPCqr/KdyLWQzkrUvkTu1LO
CPRZXV+AfmH0rkXS/xk7AgkA4L/GTu1/WeCuRdL/GTu1/WeCuRdL/GTu1/WeCuRd
L/GTu1/WQIhANPCqr/KdyLWQzkrUvkTu1LOCPRZXV+AfmH0rkXS/xk7
-----END PRIVATE KEY-----
{{- end }}

{{/*
Infrastructure readiness check
*/}}
{{- define "marty-microservice.infrastructureReady" -}}
{{- $ready := true }}
{{- if eq .Values.infrastructure.cache.backend "redis" }}
{{- if not .Values.infrastructure.cache.redis.enabled }}
{{- $ready = false }}
{{- end }}
{{- end }}
{{- if eq .Values.infrastructure.messaging.broker "rabbitmq" }}
{{- if not .Values.infrastructure.messaging.rabbitmq.enabled }}
{{- $ready = false }}
{{- end }}
{{- end }}
{{- $ready }}
{{- end }}

{{/*
Phase 2 infrastructure labels
*/}}
{{- define "marty-microservice.phase2Labels" -}}
marty.framework/cache-backend: {{ .Values.infrastructure.cache.backend }}
marty.framework/messaging-broker: {{ .Values.infrastructure.messaging.broker }}
marty.framework/events-store: {{ .Values.infrastructure.events.store }}
marty.framework/gateway-enabled: {{ .Values.infrastructure.gateway.enabled | quote }}
{{- end }}
