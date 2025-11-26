"""
Helm chart management for Marty Microservices Framework.

This module provides comprehensive Helm chart management capabilities including
chart generation, template management, values handling, and Helm deployment
orchestration for microservices architectures.
"""

import asyncio
import builtins
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import jinja2
import yaml

from .core import DeploymentConfig

logger = logging.getLogger(__name__)


class HelmAction(Enum):
    """Helm actions."""

    INSTALL = "install"
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"
    UNINSTALL = "uninstall"
    STATUS = "status"
    LIST = "list"


class ChartType(Enum):
    """Helm chart types."""

    MICROSERVICE = "microservice"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    INGRESS = "ingress"
    MONITORING = "monitoring"
    CUSTOM = "custom"


@dataclass
class HelmValues:
    """Helm chart values configuration."""

    image: builtins.dict[str, Any] = field(default_factory=dict)
    service: builtins.dict[str, Any] = field(default_factory=dict)
    ingress: builtins.dict[str, Any] = field(default_factory=dict)
    resources: builtins.dict[str, Any] = field(default_factory=dict)
    autoscaling: builtins.dict[str, Any] = field(default_factory=dict)
    config: builtins.dict[str, Any] = field(default_factory=dict)
    secrets: builtins.dict[str, Any] = field(default_factory=dict)
    persistence: builtins.dict[str, Any] = field(default_factory=dict)
    monitoring: builtins.dict[str, Any] = field(default_factory=dict)
    custom_values: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        values = {}

        for field_name in [
            "image",
            "service",
            "ingress",
            "resources",
            "autoscaling",
            "config",
            "secrets",
            "persistence",
            "monitoring",
        ]:
            field_value = getattr(self, field_name)
            if field_value:
                values[field_name] = field_value

        # Add custom values
        values.update(self.custom_values)

        return values


@dataclass
class HelmChart:
    """Helm chart definition."""

    name: str
    version: str
    chart_type: ChartType
    description: str = ""
    app_version: str | None = None
    dependencies: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    templates: builtins.dict[str, str] = field(default_factory=dict)
    values: HelmValues = field(default_factory=HelmValues)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class HelmRelease:
    """Helm release information."""

    name: str
    namespace: str
    chart: str
    version: str
    status: str
    updated: datetime
    values: builtins.dict[str, Any] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


class HelmTemplateGenerator:
    """Generates Helm chart templates."""

    def __init__(self):
        self.jinja_env = jinja2.Environment(
            loader=jinja2.DictLoader({}),
            undefined=jinja2.StrictUndefined,
            autoescape=True,
        )

    def generate_microservice_chart(self, service_name: str, config: DeploymentConfig) -> HelmChart:
        """Generate Helm chart for microservice."""
        chart = HelmChart(
            name=service_name,
            version="0.1.0",
            chart_type=ChartType.MICROSERVICE,
            description=f"Helm chart for {service_name} microservice",
            app_version=config.version,
        )

        # Generate templates
        chart.templates = {
            "deployment.yaml": self._generate_deployment_template(),
            "service.yaml": self._generate_service_template(),
            "configmap.yaml": self._generate_configmap_template(),
            "hpa.yaml": self._generate_hpa_template(),
            "ingress.yaml": self._generate_ingress_template(),
            "serviceaccount.yaml": self._generate_serviceaccount_template(),
            "_helpers.tpl": self._generate_helpers_template(),
        }

        # Generate values
        chart.values = self._generate_values_from_config(config)

        return chart

    def generate_database_chart(self, db_name: str, db_type: str) -> HelmChart:
        """Generate Helm chart for database."""
        chart = HelmChart(
            name=f"{db_name}-{db_type}",
            version="0.1.0",
            chart_type=ChartType.DATABASE,
            description=f"Helm chart for {db_name} {db_type} database",
        )

        chart.templates = {
            "statefulset.yaml": self._generate_statefulset_template(),
            "service.yaml": self._generate_database_service_template(),
            "configmap.yaml": self._generate_configmap_template(),
            "secret.yaml": self._generate_secret_template(),
            "pvc.yaml": self._generate_pvc_template(),
            "_helpers.tpl": self._generate_helpers_template(),
        }

        chart.values = self._generate_database_values(db_type)

        return chart

    def _generate_deployment_template(self) -> str:
        """Generate deployment template."""
        return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "chart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        {{- include "chart.selectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "chart.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: {{ .Values.healthCheck.path }}
              port: http
            initialDelaySeconds: {{ .Values.healthCheck.initialDelay }}
            periodSeconds: {{ .Values.healthCheck.period }}
          readinessProbe:
            httpGet:
              path: {{ .Values.healthCheck.path }}
              port: http
            initialDelaySeconds: 5
            periodSeconds: {{ .Values.healthCheck.period }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          env:
            {{- range $key, $value := .Values.config }}
            - name: {{ $key }}
              value: {{ $value | quote }}
            {{- end }}
            {{- if .Values.secrets }}
            {{- range $key, $value := .Values.secrets }}
            - name: {{ $key }}
              valueFrom:
                secretKeyRef:
                  name: {{ include "chart.fullname" $ }}-secrets
                  key: {{ $key }}
            {{- end }}
            {{- end }}
          {{- with .Values.volumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
      {{- with .Values.volumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
"""

    def _generate_service_template(self) -> str:
        """Generate service template."""
        return """apiVersion: v1
kind: Service
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "chart.selectorLabels" . | nindent 4 }}
"""

    def _generate_configmap_template(self) -> str:
        """Generate configmap template."""
        return """{{- if .Values.config }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "chart.fullname" . }}-config
  labels:
    {{- include "chart.labels" . | nindent 4 }}
data:
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
"""

    def _generate_hpa_template(self) -> str:
        """Generate HPA template."""
        return """{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "chart.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
{{- end }}
"""

    def _generate_ingress_template(self) -> str:
        """Generate ingress template."""
        return """{{- if .Values.ingress.enabled -}}
{{- $fullName := include "chart.fullname" . -}}
{{- $svcPort := .Values.service.port -}}
{{- if and .Values.ingress.className (not (hasKey .Values.ingress.annotations "kubernetes.io/ingress.class")) }}
  {{- $_ := set .Values.ingress.annotations "kubernetes.io/ingress.class" .Values.ingress.className}}
{{- end }}
{{- if semverCompare ">=1.19-0" .Capabilities.KubeVersion.GitVersion -}}
apiVersion: networking.k8s.io/v1
{{- else if semverCompare ">=1.14-0" .Capabilities.KubeVersion.GitVersion -}}
apiVersion: networking.k8s.io/v1beta1
{{- else -}}
apiVersion: extensions/v1beta1
{{- end }}
kind: Ingress
metadata:
  name: {{ $fullName }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if and .Values.ingress.className (semverCompare ">=1.18-0" .Capabilities.KubeVersion.GitVersion) }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            {{- if and .pathType (semverCompare ">=1.18-0" $.Capabilities.KubeVersion.GitVersion) }}
            pathType: {{ .pathType }}
            {{- end }}
            backend:
              {{- if semverCompare ">=1.19-0" $.Capabilities.KubeVersion.GitVersion }}
              service:
                name: {{ $fullName }}
                port:
                  number: {{ $svcPort }}
              {{- else }}
              serviceName: {{ $fullName }}
              servicePort: {{ $svcPort }}
              {{- end }}
          {{- end }}
    {{- end }}
{{- end }}
"""

    def _generate_serviceaccount_template(self) -> str:
        """Generate service account template."""
        return """{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "chart.serviceAccountName" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
"""

    def _generate_helpers_template(self) -> str:
        """Generate helpers template."""
        return """{{/*
Expand the name of the chart.
*/}}
{{- define "chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "chart.fullname" -}}
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
{{- define "chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "chart.labels" -}}
helm.sh/chart: {{ include "chart.chart" . }}
{{ include "chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
"""

    def _generate_statefulset_template(self) -> str:
        """Generate StatefulSet template for databases."""
        return """apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  serviceName: {{ include "chart.fullname" . }}
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "chart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "chart.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: database
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          env:
            {{- range $key, $value := .Values.config }}
            - name: {{ $key }}
              value: {{ $value | quote }}
            {{- end }}
            {{- if .Values.secrets }}
            {{- range $key, $value := .Values.secrets }}
            - name: {{ $key }}
              valueFrom:
                secretKeyRef:
                  name: {{ include "chart.fullname" $ }}-secrets
                  key: {{ $key }}
            {{- end }}
            {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- if .Values.persistence.enabled }}
          volumeMounts:
            - name: data
              mountPath: {{ .Values.persistence.mountPath }}
          {{- end }}
  {{- if .Values.persistence.enabled }}
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: [ "ReadWriteOnce" ]
        {{- if .Values.persistence.storageClass }}
        storageClassName: {{ .Values.persistence.storageClass }}
        {{- end }}
        resources:
          requests:
            storage: {{ .Values.persistence.size }}
  {{- end }}
"""

    def _generate_database_service_template(self) -> str:
        """Generate database service template."""
        return """apiVersion: v1
kind: Service
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  clusterIP: None
  ports:
    - port: {{ .Values.service.port }}
      targetPort: database
      protocol: TCP
      name: database
  selector:
    {{- include "chart.selectorLabels" . | nindent 4 }}
"""

    def _generate_secret_template(self) -> str:
        """Generate secret template."""
        return """{{- if .Values.secrets }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "chart.fullname" . }}-secrets
  labels:
    {{- include "chart.labels" . | nindent 4 }}
type: Opaque
data:
  {{- range $key, $value := .Values.secrets }}
  {{ $key }}: {{ $value | b64enc }}
  {{- end }}
{{- end }}
"""

    def _generate_pvc_template(self) -> str:
        """Generate PVC template."""
        return """{{- if and .Values.persistence.enabled (not .Values.persistence.existingClaim) }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "chart.fullname" . }}-data
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  accessModes:
    - {{ .Values.persistence.accessMode | quote }}
  resources:
    requests:
      storage: {{ .Values.persistence.size | quote }}
  {{- if .Values.persistence.storageClass }}
  storageClassName: {{ .Values.persistence.storageClass | quote }}
  {{- end }}
{{- end }}
"""

    def _generate_values_from_config(self, config: DeploymentConfig) -> HelmValues:
        """Generate Helm values from deployment config."""
        values = HelmValues()

        # Image configuration
        image_parts = config.image.split(":")
        repository = image_parts[0]
        tag = image_parts[1] if len(image_parts) > 1 else config.version

        values.image = {
            "repository": repository,
            "tag": tag,
            "pullPolicy": "IfNotPresent",
        }

        # Service configuration
        values.service = {"type": "ClusterIP", "port": config.health_check.port}

        # Resource configuration
        values.resources = {
            "requests": {
                "cpu": config.resources.cpu_request,
                "memory": config.resources.memory_request,
            },
            "limits": {
                "cpu": config.resources.cpu_limit,
                "memory": config.resources.memory_limit,
            },
        }

        # Autoscaling configuration
        values.autoscaling = {
            "enabled": config.resources.max_replicas > config.resources.min_replicas,
            "minReplicas": config.resources.min_replicas,
            "maxReplicas": config.resources.max_replicas,
            "targetCPUUtilizationPercentage": 70,
            "targetMemoryUtilizationPercentage": 80,
        }

        # Configuration
        values.config = config.environment_variables
        values.secrets = config.secrets

        # Health check configuration
        values.custom_values["healthCheck"] = {
            "path": config.health_check.path,
            "port": config.health_check.port,
            "initialDelay": config.health_check.initial_delay,
            "period": config.health_check.period,
        }

        # Replica count
        values.custom_values["replicaCount"] = config.resources.replicas

        # Service account
        values.custom_values["serviceAccount"] = {
            "create": bool(config.service_account),
            "name": config.service_account or "",
        }

        # Security context
        values.custom_values["securityContext"] = {}
        values.custom_values["podSecurityContext"] = {}

        return values

    def _generate_database_values(self, db_type: str) -> HelmValues:
        """Generate database-specific values."""
        values = HelmValues()

        if db_type.lower() == "postgresql":
            values.image = {
                "repository": "postgres",
                "tag": "13",
                "pullPolicy": "IfNotPresent",
            }
            values.service = {"port": 5432}
            values.config = {"POSTGRES_DB": "myapp", "POSTGRES_USER": "myapp"}
            values.secrets = {"POSTGRES_PASSWORD": "changeme"}
            values.persistence = {
                "enabled": True,
                "size": "10Gi",
                "mountPath": "/var/lib/postgresql/data",
                "accessMode": "ReadWriteOnce",
            }
        elif db_type.lower() == "redis":
            values.image = {
                "repository": "redis",
                "tag": "6-alpine",
                "pullPolicy": "IfNotPresent",
            }
            values.service = {"port": 6379}
            values.persistence = {
                "enabled": True,
                "size": "5Gi",
                "mountPath": "/data",
                "accessMode": "ReadWriteOnce",
            }

        values.custom_values["replicaCount"] = 1

        return values


class HelmManager:
    """Manages Helm operations and chart lifecycle."""

    def __init__(self, helm_binary: str = "helm", kubeconfig_path: str | None = None):
        self.helm_binary = helm_binary
        self.kubeconfig_path = kubeconfig_path
        self.template_generator = HelmTemplateGenerator()

    async def create_chart(self, chart: HelmChart, output_dir: Path) -> Path:
        """Create Helm chart on filesystem."""
        chart_dir = output_dir / chart.name
        chart_dir.mkdir(parents=True, exist_ok=True)

        # Create Chart.yaml
        chart_yaml = {
            "apiVersion": "v2",
            "name": chart.name,
            "description": chart.description,
            "version": chart.version,
            "appVersion": chart.app_version or chart.version,
            "type": "application",
        }

        if chart.dependencies:
            chart_yaml["dependencies"] = chart.dependencies

        with open(chart_dir / "Chart.yaml", "w") as f:
            yaml.dump(chart_yaml, f, default_flow_style=False)

        # Create values.yaml
        with open(chart_dir / "values.yaml", "w") as f:
            yaml.dump(chart.values.to_dict(), f, default_flow_style=False)

        # Create templates directory
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir(exist_ok=True)

        # Write templates
        for template_name, template_content in chart.templates.items():
            with open(templates_dir / template_name, "w") as f:
                f.write(template_content)

        logger.info(f"Created Helm chart: {chart_dir}")
        return chart_dir

    async def install_release(
        self,
        release_name: str,
        chart_path: str | Path,
        namespace: str,
        values: builtins.dict[str, Any] | None = None,
        wait: bool = True,
        timeout: str = "5m",
    ) -> bool:
        """Install Helm release."""
        try:
            cmd = [
                self.helm_binary,
                "install",
                release_name,
                str(chart_path),
                "--namespace",
                namespace,
                "--create-namespace",
            ]

            if values:
                # Create temporary values file
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                    yaml.dump(values, f, default_flow_style=False)
                    values_file = f.name

                cmd.extend(["--values", values_file])

            if wait:
                cmd.extend(["--wait", "--timeout", timeout])

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if values and "values_file" in locals():
                Path(values_file).unlink()  # Clean up temp file

            if result.returncode == 0:
                logger.info(f"Helm release {release_name} installed successfully")
                return True
            logger.error(f"Helm install failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Helm install error: {e}")
            return False

    async def upgrade_release(
        self,
        release_name: str,
        chart_path: str | Path,
        namespace: str,
        values: builtins.dict[str, Any] | None = None,
        wait: bool = True,
        timeout: str = "5m",
    ) -> bool:
        """Upgrade Helm release."""
        try:
            cmd = [
                self.helm_binary,
                "upgrade",
                release_name,
                str(chart_path),
                "--namespace",
                namespace,
            ]

            if values:
                # Create temporary values file
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                    yaml.dump(values, f, default_flow_style=False)
                    values_file = f.name

                cmd.extend(["--values", values_file])

            if wait:
                cmd.extend(["--wait", "--timeout", timeout])

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if values and "values_file" in locals():
                Path(values_file).unlink()  # Clean up temp file

            if result.returncode == 0:
                logger.info(f"Helm release {release_name} upgraded successfully")
                return True
            logger.error(f"Helm upgrade failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Helm upgrade error: {e}")
            return False

    async def rollback_release(
        self, release_name: str, namespace: str, revision: int | None = None
    ) -> bool:
        """Rollback Helm release."""
        try:
            cmd = [self.helm_binary, "rollback", release_name, "--namespace", namespace]

            if revision:
                cmd.append(str(revision))

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if result.returncode == 0:
                logger.info(f"Helm release {release_name} rolled back successfully")
                return True
            logger.error(f"Helm rollback failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Helm rollback error: {e}")
            return False

    async def uninstall_release(self, release_name: str, namespace: str) -> bool:
        """Uninstall Helm release."""
        try:
            cmd = [
                self.helm_binary,
                "uninstall",
                release_name,
                "--namespace",
                namespace,
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if result.returncode == 0:
                logger.info(f"Helm release {release_name} uninstalled successfully")
                return True
            logger.error(f"Helm uninstall failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Helm uninstall error: {e}")
            return False

    async def get_release_status(self, release_name: str, namespace: str) -> HelmRelease | None:
        """Get Helm release status."""
        try:
            cmd = [
                self.helm_binary,
                "status",
                release_name,
                "--namespace",
                namespace,
                "--output",
                "json",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if result.returncode == 0:
                status_data = json.loads(result.stdout)
                info = status_data.get("info", {})

                return HelmRelease(
                    name=status_data.get("name", ""),
                    namespace=status_data.get("namespace", ""),
                    chart=status_data.get("chart", {}).get("metadata", {}).get("name", ""),
                    version=status_data.get("chart", {}).get("metadata", {}).get("version", ""),
                    status=info.get("status", ""),
                    updated=datetime.fromisoformat(
                        info.get("last_deployed", "").replace("Z", "+00:00")
                    ),
                    values=status_data.get("config", {}),
                )

            return None

        except Exception as e:
            logger.error(f"Helm status error: {e}")
            return None

    async def list_releases(self, namespace: str | None = None) -> builtins.list[HelmRelease]:
        """List Helm releases."""
        try:
            cmd = [self.helm_binary, "list", "--output", "json"]

            if namespace:
                cmd.extend(["--namespace", namespace])
            else:
                cmd.append("--all-namespaces")

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if result.returncode == 0:
                releases_data = json.loads(result.stdout)
                releases = []

                for release_data in releases_data:
                    releases.append(
                        HelmRelease(
                            name=release_data.get("name", ""),
                            namespace=release_data.get("namespace", ""),
                            chart=release_data.get("chart", ""),
                            version=release_data.get("app_version", ""),
                            status=release_data.get("status", ""),
                            updated=datetime.fromisoformat(
                                release_data.get("updated", "").replace(" ", "T")
                            ),
                        )
                    )

                return releases

            return []

        except Exception as e:
            logger.error(f"Helm list error: {e}")
            return []

    async def template_chart(
        self,
        chart_path: str | Path,
        release_name: str,
        namespace: str,
        values: builtins.dict[str, Any] | None = None,
    ) -> str | None:
        """Template Helm chart to see generated manifests."""
        try:
            cmd = [
                self.helm_binary,
                "template",
                release_name,
                str(chart_path),
                "--namespace",
                namespace,
            ]

            if values:
                # Create temporary values file
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                    yaml.dump(values, f, default_flow_style=False)
                    values_file = f.name

                cmd.extend(["--values", values_file])

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_helm_command(cmd)

            if values and "values_file" in locals():
                Path(values_file).unlink()  # Clean up temp file

            if result.returncode == 0:
                return result.stdout
            logger.error(f"Helm template failed: {result.stderr}")
            return None

        except Exception as e:
            logger.error(f"Helm template error: {e}")
            return None

    async def _run_helm_command(self, cmd: builtins.list[str]) -> subprocess.CompletedProcess:
        """Run Helm command."""
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout=stdout.decode() if stdout else "",
            stderr=stderr.decode() if stderr else "",
        )

    def generate_microservice_chart(self, service_name: str, config: DeploymentConfig) -> HelmChart:
        """Generate microservice Helm chart."""
        return self.template_generator.generate_microservice_chart(service_name, config)

    def generate_database_chart(self, db_name: str, db_type: str) -> HelmChart:
        """Generate database Helm chart."""
        return self.template_generator.generate_database_chart(db_name, db_type)


# Utility functions
def create_helm_values_from_config(config: DeploymentConfig) -> builtins.dict[str, Any]:
    """Create Helm values from deployment config."""
    generator = HelmTemplateGenerator()
    values = generator._generate_values_from_config(config)
    return values.to_dict()


async def deploy_with_helm(
    manager: HelmManager, config: DeploymentConfig, chart_dir: Path | None = None
) -> builtins.tuple[bool, str | None]:
    """Deploy service using Helm."""
    try:
        # Generate chart if not provided
        if not chart_dir:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                chart = manager.generate_microservice_chart(config.service_name, config)
                chart_dir = await manager.create_chart(chart, temp_path)

        # Deploy
        release_name = f"{config.service_name}-{config.target.environment.value}"
        namespace = config.target.namespace or "default"

        # Check if release exists
        existing_release = await manager.get_release_status(release_name, namespace)

        if existing_release:
            success = await manager.upgrade_release(release_name, chart_dir, namespace)
            action = "upgraded"
        else:
            success = await manager.install_release(release_name, chart_dir, namespace)
            action = "installed"

        if success:
            return True, f"Release {release_name} {action} successfully"
        return False, f"Failed to {action} release {release_name}"

    except Exception as e:
        return False, f"Helm deployment error: {e!s}"
