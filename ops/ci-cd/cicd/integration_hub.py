"""
Pipeline Integration Hub

Provides integration capabilities for CI/CD pipelines with external systems:
- GitHub Actions, GitLab CI, Jenkins integration
- Slack, Microsoft Teams, email notifications
- JIRA, ServiceNow, PagerDuty integration
- Monitoring and observability (Prometheus, Grafana, Datadog)
- Deployment environment coordination
"""

import asyncio
import builtins
import hashlib
import hmac
import json
import smtplib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from email.mime.multipart import MimeMultipart
from email.mime.text import MimeText
from enum import Enum
from typing import Any, dict, list

import pymsteams
import requests
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    push_to_gateway,
)
from slack_sdk import WebClient

# Local imports
from . import PipelineExecution, PipelineStatus

try:
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

try:
    TEAMS_AVAILABLE = True
except ImportError:
    TEAMS_AVAILABLE = False

try:
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class IntegrationType(Enum):
    """Integration system types"""

    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"
    JIRA = "jira"
    SERVICENOW = "servicenow"
    PAGERDUTY = "pagerduty"
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"
    DATADOG = "datadog"
    WEBHOOK = "webhook"


class NotificationLevel(Enum):
    """Notification severity levels"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class IntegrationConfiguration:
    """Integration system configuration"""

    name: str
    integration_type: IntegrationType

    # Connection settings
    base_url: str = ""
    api_token: str = ""
    username: str = ""
    password: str = ""

    # Specific settings
    webhook_url: str = ""
    channel: str = ""
    team_id: str = ""
    project_key: str = ""

    # Behavior settings
    enabled: bool = True
    retry_count: int = 3
    timeout: int = 30

    # Filters
    pipeline_filters: builtins.list[str] = field(default_factory=list)
    status_filters: builtins.list[PipelineStatus] = field(default_factory=list)
    notification_levels: builtins.list[NotificationLevel] = field(default_factory=list)

    # Custom configuration
    custom_config: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "integration_type": self.integration_type.value,
            "status_filters": [s.value for s in self.status_filters],
            "notification_levels": [n.value for n in self.notification_levels],
        }


@dataclass
class NotificationMessage:
    """Notification message"""

    title: str
    content: str
    level: NotificationLevel = NotificationLevel.INFO

    # Context
    pipeline_name: str = ""
    execution_id: str = ""
    commit_sha: str = ""
    branch: str = ""

    # Formatting
    markdown: bool = True
    attachments: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    tags: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "level": self.level.value,
            "timestamp": self.timestamp.isoformat(),
        }


class IntegrationClient:
    """Base class for integration clients"""

    def __init__(self, config: IntegrationConfiguration):
        self.config = config

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send notification"""
        raise NotImplementedError

    async def update_status(self, execution: PipelineExecution) -> bool:
        """Update pipeline status in external system"""
        raise NotImplementedError

    async def create_issue(
        self, title: str, description: str, metadata: builtins.dict[str, Any]
    ) -> str | None:
        """Create issue/ticket in external system"""
        raise NotImplementedError


class SlackIntegration(IntegrationClient):
    """Slack integration client"""

    def __init__(self, config: IntegrationConfiguration):
        super().__init__(config)

        if not SLACK_AVAILABLE:
            raise ImportError("slack_sdk is required for Slack integration")

        self.client = WebClient(token=config.api_token)
        self.channel = config.channel or "#ci-cd"

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send Slack notification"""

        try:
            # Build Slack message
            color_map = {
                NotificationLevel.INFO: "#36a64f",  # Green
                NotificationLevel.SUCCESS: "#2eb886",  # Dark green
                NotificationLevel.WARNING: "#ff9500",  # Orange
                NotificationLevel.ERROR: "#e01e5a",  # Red
                NotificationLevel.CRITICAL: "#d00000",  # Dark red
            }

            color = color_map.get(message.level, "#808080")

            # Create attachment
            attachment = {
                "color": color,
                "title": message.title,
                "text": message.content,
                "footer": "Marty CI/CD Pipeline",
                "ts": int(message.timestamp.timestamp()),
            }

            # Add fields for pipeline context
            fields = []

            if message.pipeline_name:
                fields.append({"title": "Pipeline", "value": message.pipeline_name, "short": True})

            if message.execution_id:
                fields.append(
                    {
                        "title": "Execution ID",
                        "value": message.execution_id[:8],
                        "short": True,
                    }
                )

            if message.branch:
                fields.append({"title": "Branch", "value": message.branch, "short": True})

            if message.commit_sha:
                fields.append({"title": "Commit", "value": message.commit_sha[:8], "short": True})

            if fields:
                attachment["fields"] = fields

            # Add custom attachments
            attachments = [attachment] + message.attachments

            # Send message
            response = await self._send_slack_message(
                channel=self.channel,
                text=f"Pipeline {message.level.value.upper()}",
                attachments=attachments,
            )

            return response.get("ok", False)

        except Exception as e:
            print(f"❌ Failed to send Slack notification: {e}")
            return False

    async def update_status(self, execution: PipelineExecution) -> bool:
        """Update pipeline status in Slack thread"""

        try:
            # Build status message
            status_emoji = {
                PipelineStatus.PENDING: "⏳",
                PipelineStatus.RUNNING: "🔄",
                PipelineStatus.SUCCEEDED: "✅",
                PipelineStatus.FAILED: "❌",
                PipelineStatus.CANCELLED: "🛑",
            }

            emoji = status_emoji.get(execution.status, "❓")

            message = f"{emoji} Pipeline {execution.pipeline_name} is {execution.status.value}"

            if execution.duration:
                message += f" (Duration: {execution.duration:.1f}s)"

            # Send status update
            response = await self._send_slack_message(channel=self.channel, text=message)

            return response.get("ok", False)

        except Exception as e:
            print(f"❌ Failed to update Slack status: {e}")
            return False

    async def _send_slack_message(self, **kwargs) -> builtins.dict[str, Any]:
        """Send Slack message with async wrapper"""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.client.chat_postMessage(**kwargs).data)


class TeamsIntegration(IntegrationClient):
    """Microsoft Teams integration client"""

    def __init__(self, config: IntegrationConfiguration):
        super().__init__(config)

        if not TEAMS_AVAILABLE:
            raise ImportError("pymsteams is required for Teams integration")

        self.webhook_url = config.webhook_url

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send Teams notification"""

        try:
            # Create Teams message
            teams_message = pymsteams.connectorcard(self.webhook_url)

            # Set title and summary
            teams_message.title(message.title)
            teams_message.summary(message.content[:100])

            # Set color based on level
            color_map = {
                NotificationLevel.INFO: "0078D4",  # Blue
                NotificationLevel.SUCCESS: "107C10",  # Green
                NotificationLevel.WARNING: "FF8C00",  # Orange
                NotificationLevel.ERROR: "D13438",  # Red
                NotificationLevel.CRITICAL: "A4262C",  # Dark red
            }

            color = color_map.get(message.level, "808080")
            teams_message.color(color)

            # Add sections
            section = pymsteams.cardsection()
            section.text(message.content)

            # Add facts (metadata)
            if message.pipeline_name:
                section.addFact("Pipeline", message.pipeline_name)

            if message.execution_id:
                section.addFact("Execution ID", message.execution_id[:8])

            if message.branch:
                section.addFact("Branch", message.branch)

            if message.commit_sha:
                section.addFact("Commit", message.commit_sha[:8])

            teams_message.addSection(section)

            # Send message
            await self._send_teams_message(teams_message)

            return True

        except Exception as e:
            print(f"❌ Failed to send Teams notification: {e}")
            return False

    async def update_status(self, execution: PipelineExecution) -> bool:
        """Update pipeline status in Teams"""

        try:
            # Create status message
            teams_message = pymsteams.connectorcard(self.webhook_url)

            status_emoji = {
                PipelineStatus.PENDING: "⏳",
                PipelineStatus.RUNNING: "🔄",
                PipelineStatus.SUCCEEDED: "✅",
                PipelineStatus.FAILED: "❌",
                PipelineStatus.CANCELLED: "🛑",
            }

            emoji = status_emoji.get(execution.status, "❓")
            title = f"{emoji} Pipeline Status Update"

            teams_message.title(title)
            teams_message.summary(
                f"Pipeline {execution.pipeline_name} status: {execution.status.value}"
            )

            # Add status details
            section = pymsteams.cardsection()
            section.addFact("Pipeline", execution.pipeline_name)
            section.addFact("Status", execution.status.value.upper())

            if execution.duration:
                section.addFact("Duration", f"{execution.duration:.1f}s")

            if execution.completed_stages:
                section.addFact("Completed Stages", str(len(execution.completed_stages)))

            if execution.failed_stages:
                section.addFact("Failed Stages", str(len(execution.failed_stages)))

            teams_message.addSection(section)

            # Send message
            await self._send_teams_message(teams_message)

            return True

        except Exception as e:
            print(f"❌ Failed to update Teams status: {e}")
            return False

    async def _send_teams_message(self, teams_message) -> None:
        """Send Teams message with async wrapper"""

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, teams_message.send)


class EmailIntegration(IntegrationClient):
    """Email integration client"""

    def __init__(self, config: IntegrationConfiguration):
        super().__init__(config)

        self.smtp_server = config.base_url
        self.smtp_port = config.custom_config.get("port", 587)
        self.username = config.username
        self.password = config.password
        self.from_email = config.custom_config.get("from_email", config.username)
        self.to_emails = config.custom_config.get("to_emails", [])

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send email notification"""

        try:
            # Create email message
            msg = MimeMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{message.level.value.upper()}] {message.title}"

            # Create HTML content
            html_content = self._build_html_content(message)

            # Create text content
            text_content = self._build_text_content(message)

            # Attach parts
            msg.attach(MimeText(text_content, "plain"))
            msg.attach(MimeText(html_content, "html"))

            # Send email
            await self._send_email(msg)

            return True

        except Exception as e:
            print(f"❌ Failed to send email notification: {e}")
            return False

    def _build_html_content(self, message: NotificationMessage) -> str:
        """Build HTML email content"""

        color_map = {
            NotificationLevel.INFO: "#0078D4",
            NotificationLevel.SUCCESS: "#107C10",
            NotificationLevel.WARNING: "#FF8C00",
            NotificationLevel.ERROR: "#D13438",
            NotificationLevel.CRITICAL: "#A4262C",
        }

        color = color_map.get(message.level, "#808080")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
                .content {{ border: 1px solid #ddd; padding: 20px; border-radius: 0 0 5px 5px; }}
                .metadata {{ background-color: #f5f5f5; padding: 10px; margin-top: 20px; border-radius: 5px; }}
                .metadata-item {{ margin: 5px 0; }}
                .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{message.title}</h2>
            </div>
            <div class="content">
                <p>{message.content.replace(chr(10), "<br>")}</p>

                <div class="metadata">
                    <strong>Pipeline Details:</strong>
        """

        if message.pipeline_name:
            html += f'<div class="metadata-item"><strong>Pipeline:</strong> {message.pipeline_name}</div>'

        if message.execution_id:
            html += f'<div class="metadata-item"><strong>Execution ID:</strong> {message.execution_id}</div>'

        if message.branch:
            html += f'<div class="metadata-item"><strong>Branch:</strong> {message.branch}</div>'

        if message.commit_sha:
            html += (
                f'<div class="metadata-item"><strong>Commit:</strong> {message.commit_sha}</div>'
            )

        html += f"""
                </div>
            </div>
            <div class="footer">
                <p>Sent by Marty CI/CD Pipeline at {message.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
        </body>
        </html>
        """

        return html

    def _build_text_content(self, message: NotificationMessage) -> str:
        """Build plain text email content"""

        content = f"{message.title}\n"
        content += "=" * len(message.title) + "\n\n"
        content += f"{message.content}\n\n"

        content += "Pipeline Details:\n"
        content += "-" * 16 + "\n"

        if message.pipeline_name:
            content += f"Pipeline: {message.pipeline_name}\n"

        if message.execution_id:
            content += f"Execution ID: {message.execution_id}\n"

        if message.branch:
            content += f"Branch: {message.branch}\n"

        if message.commit_sha:
            content += f"Commit: {message.commit_sha}\n"

        content += (
            f"\nSent by Marty CI/CD Pipeline at {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return content

    async def _send_email(self, msg: MimeMultipart) -> None:
        """Send email with async wrapper"""

        def send_sync():
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_sync)


class WebhookIntegration(IntegrationClient):
    """Generic webhook integration client"""

    def __init__(self, config: IntegrationConfiguration):
        super().__init__(config)

        self.webhook_url = config.webhook_url
        self.headers = config.custom_config.get("headers", {})
        self.secret = config.custom_config.get("secret", "")

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send webhook notification"""

        try:
            # Build payload
            payload = {
                "type": "notification",
                "message": message.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }

            # Send webhook
            return await self._send_webhook(payload)

        except Exception as e:
            print(f"❌ Failed to send webhook notification: {e}")
            return False

    async def update_status(self, execution: PipelineExecution) -> bool:
        """Update pipeline status via webhook"""

        try:
            # Build payload
            payload = {
                "type": "status_update",
                "execution": execution.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }

            # Send webhook
            return await self._send_webhook(payload)

        except Exception as e:
            print(f"❌ Failed to update status via webhook: {e}")
            return False

    async def _send_webhook(self, payload: builtins.dict[str, Any]) -> bool:
        """Send webhook request"""

        try:
            headers = {"Content-Type": "application/json", **self.headers}

            # Add signature if secret is configured
            if self.secret:
                payload_json = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    self.secret.encode("utf-8"),
                    payload_json.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-Signature-SHA256"] = f"sha256={signature}"

            # Send request
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )

            return response.status_code < 400

        except Exception as e:
            print(f"❌ Webhook request failed: {e}")
            return False


class PrometheusIntegration(IntegrationClient):
    """Prometheus metrics integration"""

    def __init__(self, config: IntegrationConfiguration):
        super().__init__(config)

        if not PROMETHEUS_AVAILABLE:
            raise ImportError("prometheus_client is required for Prometheus integration")

        self.gateway = config.base_url
        self.job_name = config.custom_config.get("job_name", "marty_cicd")

        # Create custom registry
        self.registry = CollectorRegistry()

        # Define metrics
        self.pipeline_executions = Counter(
            "pipeline_executions_total",
            "Total number of pipeline executions",
            ["pipeline_name", "status", "branch"],
            registry=self.registry,
        )

        self.pipeline_duration = Histogram(
            "pipeline_duration_seconds",
            "Pipeline execution duration in seconds",
            ["pipeline_name", "status"],
            registry=self.registry,
        )

        self.pipeline_stage_duration = Histogram(
            "pipeline_stage_duration_seconds",
            "Pipeline stage duration in seconds",
            ["pipeline_name", "stage_name", "status"],
            registry=self.registry,
        )

        self.active_pipelines = Gauge(
            "active_pipelines",
            "Number of currently active pipelines",
            registry=self.registry,
        )

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send metrics (no notification for Prometheus)"""
        return True

    async def update_status(self, execution: PipelineExecution) -> bool:
        """Update pipeline metrics"""

        try:
            # Update execution counter
            self.pipeline_executions.labels(
                pipeline_name=execution.pipeline_name,
                status=execution.status.value,
                branch=execution.branch,
            ).inc()

            # Update duration metrics
            if execution.duration:
                self.pipeline_duration.labels(
                    pipeline_name=execution.pipeline_name, status=execution.status.value
                ).observe(execution.duration)

            # Push metrics to gateway
            await self._push_metrics()

            return True

        except Exception as e:
            print(f"❌ Failed to update Prometheus metrics: {e}")
            return False

    async def update_stage_metrics(
        self, pipeline_name: str, stage_name: str, duration: float, status: str
    ):
        """Update stage-specific metrics"""

        try:
            self.pipeline_stage_duration.labels(
                pipeline_name=pipeline_name, stage_name=stage_name, status=status
            ).observe(duration)

            await self._push_metrics()

        except Exception as e:
            print(f"❌ Failed to update stage metrics: {e}")

    async def _push_metrics(self) -> None:
        """Push metrics to Prometheus gateway"""

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: push_to_gateway(self.gateway, job=self.job_name, registry=self.registry),
        )


class PipelineIntegrationHub:
    """
    Central hub for managing pipeline integrations

    Features:
    - Multiple integration support
    - Notification routing and filtering
    - Status updates coordination
    - Metrics collection
    - Error handling and retries
    """

    def __init__(self):
        self.integrations: builtins.dict[str, IntegrationClient] = {}
        self.notification_rules: builtins.list[builtins.dict[str, Any]] = []

        # Default notification templates
        self.notification_templates = {
            "pipeline_started": {
                "title": "Pipeline Started: {pipeline_name}",
                "content": "Pipeline {pipeline_name} has started executing on branch {branch}.\n\nExecution ID: {execution_id}",
            },
            "pipeline_succeeded": {
                "title": "Pipeline Succeeded: {pipeline_name}",
                "content": "Pipeline {pipeline_name} completed successfully!\n\nDuration: {duration:.1f}s\nCompleted stages: {completed_stages}\nExecution ID: {execution_id}",
            },
            "pipeline_failed": {
                "title": "Pipeline Failed: {pipeline_name}",
                "content": "Pipeline {pipeline_name} failed during execution.\n\nFailed stages: {failed_stages}\nError: {error_message}\nExecution ID: {execution_id}",
            },
            "quality_gate_failed": {
                "title": "Quality Gate Failed: {pipeline_name}",
                "content": "Quality gate failed for pipeline {pipeline_name}.\n\nDetails: {quality_details}\nExecution ID: {execution_id}",
            },
            "deployment_started": {
                "title": "Deployment Started: {pipeline_name}",
                "content": "Deployment started for {pipeline_name} to {environment}.\n\nStrategy: {strategy}\nExecution ID: {execution_id}",
            },
        }

        print("🔗 Pipeline Integration Hub initialized")

    def add_integration(self, name: str, config: IntegrationConfiguration) -> bool:
        """Add integration client"""

        try:
            # Create integration client based on type
            if config.integration_type == IntegrationType.SLACK:
                client = SlackIntegration(config)
            elif config.integration_type == IntegrationType.TEAMS:
                client = TeamsIntegration(config)
            elif config.integration_type == IntegrationType.EMAIL:
                client = EmailIntegration(config)
            elif config.integration_type == IntegrationType.WEBHOOK:
                client = WebhookIntegration(config)
            elif config.integration_type == IntegrationType.PROMETHEUS:
                client = PrometheusIntegration(config)
            else:
                raise ValueError(f"Unsupported integration type: {config.integration_type}")

            self.integrations[name] = client
            print(f"➕ Added integration: {name} ({config.integration_type.value})")
            return True

        except Exception as e:
            print(f"❌ Failed to add integration {name}: {e}")
            return False

    def add_notification_rule(
        self,
        name: str,
        pipeline_filters: builtins.list[str] = None,
        status_filters: builtins.list[PipelineStatus] = None,
        integrations: builtins.list[str] = None,
        notification_level: NotificationLevel = NotificationLevel.INFO,
        template: str = "default",
    ):
        """Add notification rule"""

        rule = {
            "name": name,
            "pipeline_filters": pipeline_filters or [],
            "status_filters": [s.value for s in (status_filters or [])],
            "integrations": integrations or list(self.integrations.keys()),
            "notification_level": notification_level.value,
            "template": template,
        }

        self.notification_rules.append(rule)
        print(f"📋 Added notification rule: {name}")

    async def notify_pipeline_event(
        self,
        event_type: str,
        execution: PipelineExecution,
        additional_context: builtins.dict[str, Any] | None = None,
    ):
        """Send notifications for pipeline event"""

        try:
            # Find applicable notification rules
            applicable_rules = self._find_applicable_rules(execution)

            if not applicable_rules:
                return

            # Build notification message
            message = await self._build_notification_message(
                event_type, execution, additional_context or {}
            )

            # Send notifications to applicable integrations
            for rule in applicable_rules:
                for integration_name in rule["integrations"]:
                    if integration_name in self.integrations:
                        try:
                            await self.integrations[integration_name].send_notification(message)
                        except Exception as e:
                            print(f"❌ Failed to send notification via {integration_name}: {e}")

        except Exception as e:
            print(f"❌ Failed to process pipeline event notification: {e}")

    async def update_pipeline_status(self, execution: PipelineExecution):
        """Update pipeline status in all integrations"""

        try:
            # Update status in all integrations
            for name, integration in self.integrations.items():
                try:
                    await integration.update_status(execution)
                except Exception as e:
                    print(f"❌ Failed to update status in {name}: {e}")

        except Exception as e:
            print(f"❌ Failed to update pipeline status: {e}")

    def _find_applicable_rules(
        self, execution: PipelineExecution
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Find notification rules applicable to execution"""

        applicable_rules = []

        for rule in self.notification_rules:
            # Check pipeline filters
            if rule["pipeline_filters"]:
                if not any(
                    pattern in execution.pipeline_name for pattern in rule["pipeline_filters"]
                ):
                    continue

            # Check status filters
            if rule["status_filters"]:
                if execution.status.value not in rule["status_filters"]:
                    continue

            applicable_rules.append(rule)

        return applicable_rules

    async def _build_notification_message(
        self,
        event_type: str,
        execution: PipelineExecution,
        context: builtins.dict[str, Any],
    ) -> NotificationMessage:
        """Build notification message from template"""

        # Get template
        template = self.notification_templates.get(
            event_type,
            {
                "title": f"Pipeline Event: {event_type}",
                "content": "Pipeline {pipeline_name} event: {event_type}",
            },
        )

        # Build context for template
        template_context = {
            "pipeline_name": execution.pipeline_name,
            "execution_id": execution.execution_id,
            "branch": execution.branch,
            "commit_sha": execution.commit_sha,
            "status": execution.status.value,
            "duration": execution.duration or 0.0,
            "completed_stages": len(execution.completed_stages),
            "failed_stages": len(execution.failed_stages),
            "error_message": execution.error_message or "",
            **context,
        }

        # Format template
        title = template["title"].format(**template_context)
        content = template["content"].format(**template_context)

        # Determine notification level
        level = NotificationLevel.INFO

        if execution.status == PipelineStatus.SUCCEEDED:
            level = NotificationLevel.SUCCESS
        elif execution.status == PipelineStatus.FAILED:
            level = NotificationLevel.ERROR
        elif execution.status == PipelineStatus.CANCELLED:
            level = NotificationLevel.WARNING

        return NotificationMessage(
            title=title,
            content=content,
            level=level,
            pipeline_name=execution.pipeline_name,
            execution_id=execution.execution_id,
            commit_sha=execution.commit_sha,
            branch=execution.branch,
        )

    def get_integration_status(self) -> builtins.dict[str, Any]:
        """Get status of all integrations"""

        status = {
            "total_integrations": len(self.integrations),
            "integrations": {},
            "notification_rules": len(self.notification_rules),
        }

        for name, integration in self.integrations.items():
            status["integrations"][name] = {
                "type": integration.config.integration_type.value,
                "enabled": integration.config.enabled,
                "last_error": None,  # Would track in production
            }

        return status


# Example usage and demo
async def demo_pipeline_integrations():
    """Demonstration of pipeline integrations"""

    print("=== Pipeline Integration Demo ===")

    # Initialize integration hub
    hub = PipelineIntegrationHub()

    # Add Slack integration (mock)
    slack_config = IntegrationConfiguration(
        name="main_slack",
        integration_type=IntegrationType.SLACK,
        api_token="mock-token",
        channel="#ci-cd",
    )

    if SLACK_AVAILABLE:
        hub.add_integration("slack", slack_config)

    # Add webhook integration
    webhook_config = IntegrationConfiguration(
        name="webhook_integration",
        integration_type=IntegrationType.WEBHOOK,
        webhook_url="https://example.com/webhook",
        custom_config={
            "headers": {"Authorization": "Bearer token"},
            "secret": "webhook-secret",
        },
    )

    hub.add_integration("webhook", webhook_config)

    # Add email integration
    email_config = IntegrationConfiguration(
        name="email_notifications",
        integration_type=IntegrationType.EMAIL,
        base_url="smtp.gmail.com",
        username="ci@example.com",
        password="password",
        custom_config={
            "port": 587,
            "from_email": "ci@example.com",
            "to_emails": ["team@example.com"],
        },
    )

    hub.add_integration("email", email_config)

    # Add Prometheus integration (if available)
    if PROMETHEUS_AVAILABLE:
        prometheus_config = IntegrationConfiguration(
            name="metrics",
            integration_type=IntegrationType.PROMETHEUS,
            base_url="http://prometheus-gateway:9091",
            custom_config={"job_name": "marty_cicd_demo"},
        )

        hub.add_integration("prometheus", prometheus_config)

    # Add notification rules
    hub.add_notification_rule(
        name="critical_failures",
        status_filters=[PipelineStatus.FAILED],
        integrations=["slack", "email"],
        notification_level=NotificationLevel.CRITICAL,
    )

    hub.add_notification_rule(
        name="success_notifications",
        status_filters=[PipelineStatus.SUCCEEDED],
        integrations=["slack"],
        notification_level=NotificationLevel.SUCCESS,
    )

    hub.add_notification_rule(
        name="all_events",
        integrations=["webhook", "prometheus"],
        notification_level=NotificationLevel.INFO,
    )

    # Simulate pipeline events
    print("\n🎬 Simulating Pipeline Events")

    # Create mock execution
    execution = PipelineExecution(
        execution_id="demo_exec_123",
        pipeline_name="microservice_ci_cd",
        started_at=datetime.now(),
        branch="main",
        commit_sha="abc123def456",
        status=PipelineStatus.RUNNING,
    )

    # Notify pipeline started
    await hub.notify_pipeline_event("pipeline_started", execution)
    print("📢 Sent pipeline started notifications")

    # Simulate pipeline progression
    await asyncio.sleep(1)

    # Update status to success
    execution.status = PipelineStatus.SUCCEEDED
    execution.completed_at = datetime.now()
    execution.duration = 125.5
    execution.completed_stages = ["build", "test", "package", "deploy"]

    await hub.update_pipeline_status(execution)
    await hub.notify_pipeline_event("pipeline_succeeded", execution)
    print("✅ Sent pipeline success notifications")

    # Show integration status
    print("\n📊 Integration Status")

    status = hub.get_integration_status()
    print(f"Total integrations: {status['total_integrations']}")
    print(f"Notification rules: {status['notification_rules']}")

    for name, integration_status in status["integrations"].items():
        print(
            f"  - {name}: {integration_status['type']} ({'enabled' if integration_status['enabled'] else 'disabled'})"
        )

    return hub


if __name__ == "__main__":
    asyncio.run(demo_pipeline_integrations())
