"""Elasticsearch SIEM adapter implementation."""

import json
from datetime import datetime
from typing import Any

from mmf_new.core.infrastructure.database import DatabaseManager

from ...domain.contracts import ISIEMAdapter


class ElasticsearchSIEMAdapter(ISIEMAdapter):
    """Elasticsearch implementation of SIEM adapter."""

    def __init__(self, elasticsearch_client, index_prefix: str = "marty-security"):
        self.elasticsearch = elasticsearch_client
        self.index_prefix = index_prefix

    async def send_event(self, event_data: dict[str, Any]) -> bool:
        """Send a single event to Elasticsearch."""
        try:
            # Create index name with current date
            index_name = f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"

            # Prepare event for Elasticsearch
            es_event = self._prepare_elasticsearch_event(event_data)

            # Index the event
            response = await self.elasticsearch.index(index=index_name, document=es_event)

            return response.get("result") in ["created", "updated"]

        except Exception as e:
            # Log error but don't fail the entire operation
            print(f"Failed to send event to Elasticsearch: {e}")
            return False

    async def send_events(self, events: list[dict[str, Any]]) -> int:
        """Send multiple events to Elasticsearch in batch."""
        if not events:
            return 0

        try:
            # Create index name with current date
            index_name = f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"

            # Prepare bulk request
            bulk_body = []
            for event_data in events:
                es_event = self._prepare_elasticsearch_event(event_data)

                # Add index action
                bulk_body.append(
                    {
                        "index": {
                            "_index": index_name,
                            "_id": es_event.get("event_id"),  # Use event ID if available
                        }
                    }
                )
                bulk_body.append(es_event)

            # Execute bulk request
            response = await self.elasticsearch.bulk(body=bulk_body)

            # Count successful operations
            successful = 0
            if response.get("items"):
                for item in response["items"]:
                    if "index" in item:
                        if item["index"].get("status") in [200, 201]:
                            successful += 1

            return successful

        except Exception as e:
            print(f"Failed to send batch events to Elasticsearch: {e}")
            return 0

    async def query_events(self, query: dict[str, Any], size: int = 100) -> list[dict[str, Any]]:
        """Query events from Elasticsearch."""
        try:
            # Use all security indices if no specific index is provided
            index_pattern = f"{self.index_prefix}-*"

            # Execute search
            response = await self.elasticsearch.search(
                index=index_pattern, body=query, size=size, sort=[{"@timestamp": {"order": "desc"}}]
            )

            # Extract hits
            events = []
            if response.get("hits", {}).get("hits"):
                for hit in response["hits"]["hits"]:
                    event = hit["_source"]
                    event["_id"] = hit["_id"]
                    event["_index"] = hit["_index"]
                    events.append(event)

            return events

        except Exception as e:
            print(f"Failed to query events from Elasticsearch: {e}")
            return []

    async def create_alert(self, alert_data: dict[str, Any]) -> bool:
        """Create an alert in Elasticsearch."""
        try:
            # Create alerts index
            alert_index = f"{self.index_prefix}-alerts-{datetime.now().strftime('%Y.%m')}"

            # Prepare alert document
            alert_doc = {
                "@timestamp": datetime.utcnow().isoformat(),
                "alert": {
                    "id": alert_data.get("id"),
                    "title": alert_data.get("title", "Security Alert"),
                    "description": alert_data.get("description", ""),
                    "severity": alert_data.get("severity", "medium"),
                    "status": alert_data.get("status", "open"),
                    "category": alert_data.get("category", "security"),
                },
                "event": alert_data.get("event", {}),
                "source": alert_data.get("source", {}),
                "destination": alert_data.get("destination", {}),
                "user": alert_data.get("user", {}),
                "network": alert_data.get("network", {}),
                "process": alert_data.get("process", {}),
                "file": alert_data.get("file", {}),
                "tags": alert_data.get("tags", []),
                "metadata": alert_data.get("metadata", {}),
            }

            # Index the alert
            response = await self.elasticsearch.index(index=alert_index, document=alert_doc)

            return response.get("result") in ["created", "updated"]

        except Exception as e:
            print(f"Failed to create alert in Elasticsearch: {e}")
            return False

    async def get_connection_status(self) -> dict[str, Any]:
        """Get the connection status to Elasticsearch."""
        try:
            # Perform cluster health check
            health = await self.elasticsearch.cluster.health()

            # Get cluster info
            info = await self.elasticsearch.info()

            return {
                "connected": True,
                "cluster_name": health.get("cluster_name"),
                "status": health.get("status"),
                "number_of_nodes": health.get("number_of_nodes"),
                "elasticsearch_version": info.get("version", {}).get("number"),
                "last_check": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
            }

    def _prepare_elasticsearch_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare event data for Elasticsearch indexing following ECS format."""
        # Extract basic event information
        event_type = event_data.get("event_type", "security_event")
        timestamp = event_data.get("timestamp", datetime.utcnow().isoformat())

        # Build ECS-compliant document
        es_event = {
            "@timestamp": timestamp,
            "event": {
                "id": event_data.get("event_id"),
                "type": event_type,
                "category": ["security"],
                "kind": "event",
                "severity": self._map_severity_to_ecs(event_data.get("severity", "medium")),
                "outcome": event_data.get("result", "unknown"),
                "action": event_data.get("action"),
                "dataset": "marty.audit_compliance",
                "module": "audit_compliance",
            },
            "service": {
                "name": event_data.get("source_system", "marty-framework"),
                "type": "security",
            },
            "tags": ["marty", "security", "audit"],
        }

        # Add user information if available
        if event_data.get("principal_id"):
            es_event["user"] = {
                "id": event_data["principal_id"],
                "name": event_data.get("principal_name", event_data["principal_id"]),
            }

        # Add resource information
        if event_data.get("resource"):
            es_event["url"] = {
                "path": event_data["resource"],
            }

        # Add network information if available
        if event_data.get("details"):
            details = event_data["details"]

            # IP address
            if details.get("enriched_data", {}).get("ip_address"):
                es_event["source"] = {"ip": details["enriched_data"]["ip_address"]}

            # User agent
            if details.get("enriched_data", {}).get("user_agent"):
                es_event["user_agent"] = {"original": details["enriched_data"]["user_agent"]}

            # HTTP information
            if details.get("original_event", {}).get("response_code"):
                es_event["http"] = {
                    "response": {"status_code": details["original_event"]["response_code"]}
                }

        # Add correlation information
        if event_data.get("correlation_id"):
            es_event["event"]["correlation_id"] = event_data["correlation_id"]

        # Add analysis results if available
        if event_data.get("analysis"):
            es_event["marty"] = {"analysis": event_data["analysis"]}

        # Add raw details
        es_event["marty_raw"] = {
            "original_event": event_data.get("details", {}),
            "level": event_data.get("level"),
        }

        return es_event

    def _map_severity_to_ecs(self, severity: str) -> int:
        """Map internal severity to ECS severity level."""
        severity_mapping = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "info": 0,
        }

        return severity_mapping.get(severity.lower(), 2)

    async def search_security_events(
        self,
        filters: dict[str, Any],
        time_range: dict[str, Any] | None = None,
        size: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for security events with specific filters."""
        try:
            # Build Elasticsearch query
            query = {"bool": {"must": [], "filter": []}}

            # Add time range filter
            if time_range:
                time_filter = {"range": {"@timestamp": {}}}
                if time_range.get("gte"):
                    time_filter["range"]["@timestamp"]["gte"] = time_range["gte"]
                if time_range.get("lte"):
                    time_filter["range"]["@timestamp"]["lte"] = time_range["lte"]

                query["bool"]["filter"].append(time_filter)

            # Add field filters
            for field, value in filters.items():
                if field == "event_type":
                    query["bool"]["must"].append({"term": {"event.type": value}})
                elif field == "severity":
                    query["bool"]["must"].append(
                        {"term": {"event.severity": self._map_severity_to_ecs(value)}}
                    )
                elif field == "principal_id":
                    query["bool"]["must"].append({"term": {"user.id": value}})
                elif field == "resource":
                    query["bool"]["must"].append({"term": {"url.path": value}})
                elif field == "source_ip":
                    query["bool"]["must"].append({"term": {"source.ip": value}})

            # Execute search
            search_body = {"query": query, "sort": [{"@timestamp": {"order": "desc"}}]}

            return await self.query_events(search_body, size)

        except Exception as e:
            print(f"Failed to search security events: {e}")
            return []

    async def create_index_template(self) -> bool:
        """Create index template for security events."""
        try:
            template_name = f"{self.index_prefix}-template"

            template_body = {
                "index_patterns": [f"{self.index_prefix}-*"],
                "template": {
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "refresh_interval": "5s",
                    },
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "event": {
                                "properties": {
                                    "id": {"type": "keyword"},
                                    "type": {"type": "keyword"},
                                    "category": {"type": "keyword"},
                                    "severity": {"type": "integer"},
                                    "outcome": {"type": "keyword"},
                                    "action": {"type": "keyword"},
                                }
                            },
                            "user": {
                                "properties": {
                                    "id": {"type": "keyword"},
                                    "name": {"type": "keyword"},
                                }
                            },
                            "source": {"properties": {"ip": {"type": "ip"}}},
                            "url": {"properties": {"path": {"type": "keyword"}}},
                            "service": {
                                "properties": {
                                    "name": {"type": "keyword"},
                                    "type": {"type": "keyword"},
                                }
                            },
                            "marty": {"properties": {"analysis": {"type": "object"}}},
                            "marty_raw": {"type": "object"},
                            "tags": {"type": "keyword"},
                        }
                    },
                },
            }

            response = await self.elasticsearch.indices.put_template(
                name=template_name, body=template_body
            )

            return response.get("acknowledged", False)

        except Exception as e:
            print(f"Failed to create index template: {e}")
            return False
