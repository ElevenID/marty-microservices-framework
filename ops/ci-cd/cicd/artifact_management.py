"""
Artifact Management System for CI/CD Pipelines

Provides comprehensive artifact lifecycle management including:
- Artifact storage and retrieval
- Version management and tagging
- Multi-backend storage support (local, S3, GCS, Azure, registries)
- Artifact promotion between environments
- Retention policies and cleanup
- Security and access control
"""

import asyncio
import builtins
import gzip
import hashlib
import importlib.util
import json
import mimetypes
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, dict, list

import boto3

from . import ArtifactType

# External dependencies
try:
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    # Storage backend availability checks

    GCS_AVAILABLE = importlib.util.find_spec("google.cloud.storage") is not None
except ImportError:
    GCS_AVAILABLE = False

try:
    # Azure storage availability check
    AZURE_AVAILABLE = importlib.util.find_spec("azure.storage.blob") is not None
except ImportError:
    AZURE_AVAILABLE = False

try:
    # Docker availability check
    DOCKER_AVAILABLE = importlib.util.find_spec("docker") is not None
except ImportError:
    DOCKER_AVAILABLE = False


# Local imports


class StorageBackend(Enum):
    """Artifact storage backend types"""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    DOCKER_REGISTRY = "docker_registry"
    ARTIFACTORY = "artifactory"
    NEXUS = "nexus"


class PromotionStatus(Enum):
    """Artifact promotion status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StorageConfiguration:
    """Storage backend configuration"""

    backend: StorageBackend

    # Common settings
    bucket_name: str = ""
    base_path: str = ""

    # Authentication
    access_key: str = ""
    secret_key: str = ""
    region: str = ""

    # Advanced settings
    encryption_enabled: bool = True
    compression_enabled: bool = True
    multipart_threshold: int = 100 * 1024 * 1024  # 100MB

    # Backend-specific configuration
    config: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "backend": self.backend.value}


@dataclass
class ArtifactMetadata:
    """Extended artifact metadata"""

    artifact_id: str
    pipeline_execution_id: str

    # Core metadata
    name: str
    version: str
    artifact_type: ArtifactType

    # File information
    file_path: str
    file_size: int
    checksum_sha256: str
    content_type: str

    # Lifecycle
    created_at: datetime
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None

    # Classification
    tags: builtins.dict[str, str] = field(default_factory=dict)
    labels: builtins.dict[str, str] = field(default_factory=dict)
    environment: str = "development"

    # Promotion tracking
    promoted_from: str | None = None
    promoted_to: builtins.list[str] = field(default_factory=list)

    # Security
    access_level: str = "internal"  # public, internal, restricted, confidential
    encryption_key_id: str | None = None

    # Custom metadata
    custom_metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "artifact_type": self.artifact_type.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat()
            if self.last_accessed_at
            else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class PromotionRequest:
    """Artifact promotion request"""

    request_id: str
    artifact_id: str
    source_environment: str
    target_environment: str

    # Request details
    requested_by: str
    requested_at: datetime
    reason: str = ""

    # Approval workflow
    approval_required: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None

    # Execution
    status: PromotionStatus = PromotionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    target_artifact_id: str | None = None
    error_message: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class RetentionPolicy:
    """Artifact retention policy"""

    name: str
    description: str = ""

    # Retention rules
    max_age_days: int | None = None
    max_versions: int | None = None
    max_size_mb: int | None = None

    # Filters
    artifact_types: builtins.list[ArtifactType] = field(default_factory=list)
    environments: builtins.list[str] = field(default_factory=list)
    tag_filters: builtins.dict[str, str] = field(default_factory=dict)

    # Actions
    delete_expired: bool = True
    archive_before_delete: bool = True
    notify_before_delete: bool = True

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "artifact_types": [t.value for t in self.artifact_types],
        }


class ArtifactStorageBackend:
    """Base class for artifact storage backends"""

    def __init__(self, config: StorageConfiguration):
        self.config = config

    async def store_artifact(
        self, artifact_metadata: ArtifactMetadata, file_path: str
    ) -> builtins.dict[str, Any]:
        """Store artifact in backend"""
        raise NotImplementedError

    async def retrieve_artifact(self, artifact_id: str, destination_path: str) -> bool:
        """Retrieve artifact from backend"""
        raise NotImplementedError

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact from backend"""
        raise NotImplementedError

    async def list_artifacts(self, prefix: str = "", limit: int = 100) -> builtins.list[str]:
        """List artifacts in backend"""
        raise NotImplementedError

    async def get_artifact_info(self, artifact_id: str) -> builtins.dict[str, Any] | None:
        """Get artifact information from backend"""
        raise NotImplementedError


class LocalStorageBackend(ArtifactStorageBackend):
    """Local filesystem storage backend"""

    def __init__(self, config: StorageConfiguration):
        super().__init__(config)
        self.base_path = Path(config.base_path or "./artifacts")
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store_artifact(
        self, artifact_metadata: ArtifactMetadata, file_path: str
    ) -> builtins.dict[str, Any]:
        """Store artifact locally"""

        try:
            # Create artifact directory
            artifact_dir = (
                self.base_path / artifact_metadata.environment / artifact_metadata.artifact_id
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Copy artifact file
            source_path = Path(file_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {file_path}")

            destination_path = artifact_dir / source_path.name

            if self.config.compression_enabled and source_path.suffix not in [
                ".gz",
                ".zip",
                ".tar",
            ]:
                # Compress artifact
                compressed_path = destination_path.with_suffix(destination_path.suffix + ".gz")
                await self._compress_file(source_path, compressed_path)
                destination_path = compressed_path
            else:
                shutil.copy2(source_path, destination_path)

            # Store metadata
            metadata_path = artifact_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(artifact_metadata.to_dict(), f, indent=2)

            # Calculate final size and checksum
            file_size = destination_path.stat().st_size
            checksum = await self._calculate_checksum(destination_path)

            return {
                "storage_path": str(destination_path),
                "file_size": file_size,
                "checksum": checksum,
                "metadata_path": str(metadata_path),
            }

        except Exception as e:
            raise Exception(f"Failed to store artifact locally: {e}")

    async def retrieve_artifact(self, artifact_id: str, destination_path: str) -> bool:
        """Retrieve artifact from local storage"""

        try:
            # Find artifact directory
            artifact_dirs = list(self.base_path.glob(f"*/{artifact_id}"))
            if not artifact_dirs:
                return False

            artifact_dir = artifact_dirs[0]

            # Find artifact file (exclude metadata)
            artifact_files = [
                f for f in artifact_dir.iterdir() if f.is_file() and f.name != "metadata.json"
            ]

            if not artifact_files:
                return False

            artifact_file = artifact_files[0]
            destination = Path(destination_path)

            # Decompress if needed
            if artifact_file.suffix == ".gz" and destination.suffix != ".gz":
                await self._decompress_file(artifact_file, destination)
            else:
                shutil.copy2(artifact_file, destination)

            return True

        except Exception as e:
            print(f"Failed to retrieve artifact: {e}")
            return False

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact from local storage"""

        try:
            artifact_dirs = list(self.base_path.glob(f"*/{artifact_id}"))

            for artifact_dir in artifact_dirs:
                shutil.rmtree(artifact_dir)

            return True

        except Exception as e:
            print(f"Failed to delete artifact: {e}")
            return False

    async def list_artifacts(self, prefix: str = "", limit: int = 100) -> builtins.list[str]:
        """List artifacts in local storage"""

        artifacts = []

        for env_dir in self.base_path.iterdir():
            if not env_dir.is_dir():
                continue

            for artifact_dir in env_dir.iterdir():
                if not artifact_dir.is_dir():
                    continue

                artifact_id = artifact_dir.name
                if prefix and not artifact_id.startswith(prefix):
                    continue

                artifacts.append(artifact_id)

                if len(artifacts) >= limit:
                    break

            if len(artifacts) >= limit:
                break

        return artifacts

    async def get_artifact_info(self, artifact_id: str) -> builtins.dict[str, Any] | None:
        """Get artifact information"""

        try:
            artifact_dirs = list(self.base_path.glob(f"*/{artifact_id}"))
            if not artifact_dirs:
                return None

            artifact_dir = artifact_dirs[0]
            metadata_path = artifact_dir / "metadata.json"

            if not metadata_path.exists():
                return None

            with open(metadata_path) as f:
                metadata = json.load(f)

            return metadata

        except Exception as e:
            print(f"Failed to get artifact info: {e}")
            return None

    async def _compress_file(self, source_path: Path, destination_path: Path):
        """Compress file using gzip"""

        with open(source_path, "rb") as f_in:
            with gzip.open(destination_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    async def _decompress_file(self, source_path: Path, destination_path: Path):
        """Decompress gzip file"""

        with gzip.open(source_path, "rb") as f_in:
            with open(destination_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum"""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()


class S3StorageBackend(ArtifactStorageBackend):
    """AWS S3 storage backend"""

    def __init__(self, config: StorageConfiguration):
        super().__init__(config)

        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required for S3 storage backend")

        # Initialize S3 client
        session = boto3.Session(
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
        )
        self.s3_client = session.client("s3")
        self.bucket_name = config.bucket_name

    async def store_artifact(
        self, artifact_metadata: ArtifactMetadata, file_path: str
    ) -> builtins.dict[str, Any]:
        """Store artifact in S3"""

        try:
            # Build S3 key
            s3_key = f"{self.config.base_path}/{artifact_metadata.environment}/{artifact_metadata.artifact_id}/{Path(file_path).name}"

            # Prepare upload arguments
            upload_args = {
                "Metadata": {
                    "artifact-id": artifact_metadata.artifact_id,
                    "artifact-type": artifact_metadata.artifact_type.value,
                    "version": artifact_metadata.version,
                    "environment": artifact_metadata.environment,
                }
            }

            if self.config.encryption_enabled:
                upload_args["ServerSideEncryption"] = "AES256"

            # Upload file
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key, ExtraArgs=upload_args)

            # Store metadata separately
            metadata_key = f"{s3_key}.metadata.json"
            metadata_json = json.dumps(artifact_metadata.to_dict(), indent=2)

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=metadata_json,
                ContentType="application/json",
            )

            # Get object info for return
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            return {
                "storage_path": f"s3://{self.bucket_name}/{s3_key}",
                "file_size": response["ContentLength"],
                "etag": response["ETag"].strip('"'),
                "metadata_path": f"s3://{self.bucket_name}/{metadata_key}",
            }

        except Exception as e:
            raise Exception(f"Failed to store artifact in S3: {e}")

    async def retrieve_artifact(self, artifact_id: str, destination_path: str) -> bool:
        """Retrieve artifact from S3"""

        try:
            # Find artifact by listing objects
            prefix = f"{self.config.base_path}/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            artifact_key = None
            for obj in response.get("Contents", []):
                if artifact_id in obj["Key"] and not obj["Key"].endswith(".metadata.json"):
                    artifact_key = obj["Key"]
                    break

            if not artifact_key:
                return False

            # Download artifact
            self.s3_client.download_file(self.bucket_name, artifact_key, destination_path)

            return True

        except Exception as e:
            print(f"Failed to retrieve artifact from S3: {e}")
            return False

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact from S3"""

        try:
            # Find all objects for this artifact
            prefix = f"{self.config.base_path}/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            delete_objects = []
            for obj in response.get("Contents", []):
                if artifact_id in obj["Key"]:
                    delete_objects.append({"Key": obj["Key"]})

            if delete_objects:
                self.s3_client.delete_objects(
                    Bucket=self.bucket_name, Delete={"Objects": delete_objects}
                )

            return True

        except Exception as e:
            print(f"Failed to delete artifact from S3: {e}")
            return False

    async def list_artifacts(self, prefix: str = "", limit: int = 100) -> builtins.list[str]:
        """List artifacts in S3"""

        try:
            list_prefix = f"{self.config.base_path}/"
            if prefix:
                list_prefix += prefix

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=list_prefix, MaxKeys=limit
            )

            artifacts = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".metadata.json"):
                    # Extract artifact ID from key
                    parts = key.split("/")
                    if len(parts) >= 3:
                        artifact_id = parts[-2]
                        if artifact_id not in artifacts:
                            artifacts.append(artifact_id)

            return artifacts

        except Exception as e:
            print(f"Failed to list artifacts in S3: {e}")
            return []

    async def get_artifact_info(self, artifact_id: str) -> builtins.dict[str, Any] | None:
        """Get artifact information from S3"""

        try:
            # Find metadata file
            prefix = f"{self.config.base_path}/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            metadata_key = None
            for obj in response.get("Contents", []):
                if artifact_id in obj["Key"] and obj["Key"].endswith(".metadata.json"):
                    metadata_key = obj["Key"]
                    break

            if not metadata_key:
                return None

            # Download metadata
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=metadata_key)

            metadata = json.loads(response["Body"].read().decode("utf-8"))
            return metadata

        except Exception as e:
            print(f"Failed to get artifact info from S3: {e}")
            return None


class ArtifactManager:
    """
    Central artifact management system

    Features:
    - Multi-backend storage support
    - Artifact lifecycle management
    - Version and promotion management
    - Retention policies
    - Security and access control
    """

    def __init__(self, default_storage_config: StorageConfiguration):
        self.default_storage_config = default_storage_config
        self.storage_backends: builtins.dict[str, ArtifactStorageBackend] = {}

        # Initialize default backend
        self.storage_backends["default"] = self._create_storage_backend(default_storage_config)

        # Artifact registry
        self.artifacts: builtins.dict[str, ArtifactMetadata] = {}
        self.promotion_requests: builtins.dict[str, PromotionRequest] = {}
        self.retention_policies: builtins.list[RetentionPolicy] = []

        print(f"🗃️ Artifact Manager initialized with {default_storage_config.backend.value} backend")

    def _create_storage_backend(self, config: StorageConfiguration) -> ArtifactStorageBackend:
        """Create storage backend instance"""

        if config.backend == StorageBackend.LOCAL:
            return LocalStorageBackend(config)
        if config.backend == StorageBackend.S3:
            return S3StorageBackend(config)
        raise ValueError(f"Unsupported storage backend: {config.backend}")

    def add_storage_backend(self, name: str, config: StorageConfiguration):
        """Add additional storage backend"""
        self.storage_backends[name] = self._create_storage_backend(config)
        print(f"📦 Added storage backend: {name} ({config.backend.value})")

    async def store_artifact(
        self,
        pipeline_execution_id: str,
        name: str,
        version: str,
        artifact_type: ArtifactType,
        file_path: str,
        environment: str = "development",
        tags: builtins.dict[str, str] | None = None,
        labels: builtins.dict[str, str] | None = None,
        backend_name: str = "default",
        custom_metadata: builtins.dict[str, Any] | None = None,
    ) -> str:
        """Store artifact in specified backend"""

        # Generate artifact ID
        artifact_id = (
            f"{name}_{version}_{int(datetime.now().timestamp())}_{hash(file_path) % 10000:04d}"
        )

        # Calculate file metadata
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Artifact file not found: {file_path}")

        file_size = file_path_obj.stat().st_size
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        # Calculate checksum
        checksum = await self._calculate_file_checksum(file_path)

        # Create metadata
        artifact_metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            pipeline_execution_id=pipeline_execution_id,
            name=name,
            version=version,
            artifact_type=artifact_type,
            file_path=str(file_path_obj),
            file_size=file_size,
            checksum_sha256=checksum,
            content_type=content_type,
            created_at=datetime.now(),
            environment=environment,
            tags=tags or {},
            labels=labels or {},
            custom_metadata=custom_metadata or {},
        )

        # Store in backend
        if backend_name not in self.storage_backends:
            raise ValueError(f"Storage backend not found: {backend_name}")

        backend = self.storage_backends[backend_name]

        try:
            storage_result = await backend.store_artifact(artifact_metadata, file_path)

            # Update metadata with storage information
            artifact_metadata.file_path = storage_result.get("storage_path", file_path)
            artifact_metadata.file_size = storage_result.get("file_size", file_size)
            if "checksum" in storage_result:
                artifact_metadata.checksum_sha256 = storage_result["checksum"]

            # Register artifact
            self.artifacts[artifact_id] = artifact_metadata

            print(f"📦 Stored artifact: {artifact_id} ({artifact_type.value}) in {backend_name}")
            return artifact_id

        except Exception as e:
            raise Exception(f"Failed to store artifact: {e}")

    async def retrieve_artifact(
        self, artifact_id: str, destination_path: str, backend_name: str = "default"
    ) -> bool:
        """Retrieve artifact from storage"""

        if artifact_id not in self.artifacts:
            print(f"❌ Artifact not found: {artifact_id}")
            return False

        if backend_name not in self.storage_backends:
            print(f"❌ Storage backend not found: {backend_name}")
            return False

        backend = self.storage_backends[backend_name]

        try:
            success = await backend.retrieve_artifact(artifact_id, destination_path)

            if success:
                # Update last accessed time
                self.artifacts[artifact_id].last_accessed_at = datetime.now()
                print(f"📥 Retrieved artifact: {artifact_id}")
            else:
                print(f"❌ Failed to retrieve artifact: {artifact_id}")

            return success

        except Exception as e:
            print(f"❌ Error retrieving artifact: {e}")
            return False

    async def promote_artifact(
        self,
        artifact_id: str,
        target_environment: str,
        requested_by: str,
        reason: str = "",
        approval_required: bool = True,
    ) -> str:
        """Create artifact promotion request"""

        if artifact_id not in self.artifacts:
            raise ValueError(f"Artifact not found: {artifact_id}")

        artifact = self.artifacts[artifact_id]

        # Generate promotion request ID
        request_id = f"promo_{artifact_id}_{target_environment}_{int(datetime.now().timestamp())}"

        # Create promotion request
        promotion_request = PromotionRequest(
            request_id=request_id,
            artifact_id=artifact_id,
            source_environment=artifact.environment,
            target_environment=target_environment,
            requested_by=requested_by,
            requested_at=datetime.now(),
            reason=reason,
            approval_required=approval_required,
        )

        self.promotion_requests[request_id] = promotion_request

        print(f"🚀 Created promotion request: {request_id}")

        # Auto-execute if no approval required
        if not approval_required:
            await self.execute_promotion(request_id, requested_by)

        return request_id

    async def approve_promotion(self, request_id: str, approved_by: str) -> bool:
        """Approve artifact promotion request"""

        if request_id not in self.promotion_requests:
            return False

        promotion_request = self.promotion_requests[request_id]

        if promotion_request.status != PromotionStatus.PENDING:
            return False

        promotion_request.approved_by = approved_by
        promotion_request.approved_at = datetime.now()

        # Execute promotion
        await self.execute_promotion(request_id, approved_by)

        return True

    async def execute_promotion(self, request_id: str, executor: str) -> bool:
        """Execute artifact promotion"""

        if request_id not in self.promotion_requests:
            return False

        promotion_request = self.promotion_requests[request_id]

        if promotion_request.approval_required and not promotion_request.approved_by:
            promotion_request.status = PromotionStatus.FAILED
            promotion_request.error_message = "Promotion not approved"
            return False

        try:
            promotion_request.status = PromotionStatus.IN_PROGRESS
            promotion_request.started_at = datetime.now()

            # Get source artifact
            source_artifact = self.artifacts[promotion_request.artifact_id]

            # Create temporary file for artifact
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                # Retrieve artifact
                success = await self.retrieve_artifact(promotion_request.artifact_id, temp_path)

                if not success:
                    raise Exception("Failed to retrieve source artifact")

                # Create new artifact in target environment
                target_artifact_id = await self.store_artifact(
                    pipeline_execution_id=source_artifact.pipeline_execution_id,
                    name=source_artifact.name,
                    version=source_artifact.version,
                    artifact_type=source_artifact.artifact_type,
                    file_path=temp_path,
                    environment=promotion_request.target_environment,
                    tags=source_artifact.tags,
                    labels=source_artifact.labels,
                    custom_metadata={
                        **source_artifact.custom_metadata,
                        "promoted_from": promotion_request.artifact_id,
                        "promoted_by": executor,
                        "promotion_request_id": request_id,
                    },
                )

                # Update promotion tracking
                source_artifact.promoted_to.append(target_artifact_id)
                self.artifacts[target_artifact_id].promoted_from = promotion_request.artifact_id

                # Complete promotion
                promotion_request.status = PromotionStatus.COMPLETED
                promotion_request.completed_at = datetime.now()
                promotion_request.target_artifact_id = target_artifact_id

                print(
                    f"✅ Artifact promoted: {promotion_request.artifact_id} -> {target_artifact_id}"
                )
                return True

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            promotion_request.status = PromotionStatus.FAILED
            promotion_request.completed_at = datetime.now()
            promotion_request.error_message = str(e)
            print(f"❌ Promotion failed: {e}")
            return False

    async def delete_artifact(self, artifact_id: str, backend_name: str = "default") -> bool:
        """Delete artifact from storage"""

        if artifact_id not in self.artifacts:
            print(f"❌ Artifact not found: {artifact_id}")
            return False

        if backend_name not in self.storage_backends:
            print(f"❌ Storage backend not found: {backend_name}")
            return False

        backend = self.storage_backends[backend_name]

        try:
            success = await backend.delete_artifact(artifact_id)

            if success:
                # Remove from registry
                del self.artifacts[artifact_id]
                print(f"🗑️ Deleted artifact: {artifact_id}")
            else:
                print(f"❌ Failed to delete artifact: {artifact_id}")

            return success

        except Exception as e:
            print(f"❌ Error deleting artifact: {e}")
            return False

    def add_retention_policy(self, policy: RetentionPolicy):
        """Add artifact retention policy"""
        self.retention_policies.append(policy)
        print(f"📋 Added retention policy: {policy.name}")

    async def apply_retention_policies(self) -> builtins.dict[str, Any]:
        """Apply retention policies to artifacts"""

        results = {
            "policies_applied": 0,
            "artifacts_processed": 0,
            "artifacts_deleted": 0,
            "artifacts_archived": 0,
            "errors": [],
        }

        for policy in self.retention_policies:
            try:
                policy_result = await self._apply_retention_policy(policy)
                results["policies_applied"] += 1
                results["artifacts_processed"] += policy_result["processed"]
                results["artifacts_deleted"] += policy_result["deleted"]
                results["artifacts_archived"] += policy_result["archived"]

            except Exception as e:
                results["errors"].append(f"Policy {policy.name}: {e}")

        print(
            f"🧹 Retention policies applied: {results['artifacts_deleted']} deleted, {results['artifacts_archived']} archived"
        )
        return results

    async def _apply_retention_policy(self, policy: RetentionPolicy) -> builtins.dict[str, int]:
        """Apply single retention policy"""

        result = {"processed": 0, "deleted": 0, "archived": 0}
        current_time = datetime.now()

        # Filter artifacts based on policy criteria
        filtered_artifacts = []

        for artifact_id, artifact in self.artifacts.items():
            # Check artifact type filter
            if policy.artifact_types and artifact.artifact_type not in policy.artifact_types:
                continue

            # Check environment filter
            if policy.environments and artifact.environment not in policy.environments:
                continue

            # Check tag filters
            if policy.tag_filters:
                if not all(
                    artifact.tags.get(key) == value for key, value in policy.tag_filters.items()
                ):
                    continue

            filtered_artifacts.append((artifact_id, artifact))

        result["processed"] = len(filtered_artifacts)

        # Apply retention rules
        for artifact_id, artifact in filtered_artifacts:
            should_delete = False

            # Check age-based retention
            if policy.max_age_days:
                age_days = (current_time - artifact.created_at).days
                if age_days > policy.max_age_days:
                    should_delete = True

            # Check explicit expiration
            if artifact.expires_at and current_time > artifact.expires_at:
                should_delete = True

            if should_delete:
                if policy.archive_before_delete:
                    # Archive artifact (implementation would depend on archive strategy)
                    result["archived"] += 1

                if policy.delete_expired:
                    await self.delete_artifact(artifact_id)
                    result["deleted"] += 1

        # Apply version-based retention (keep only latest N versions)
        if policy.max_versions:
            # Group artifacts by name
            artifact_groups = {}
            for artifact_id, artifact in filtered_artifacts:
                if artifact.name not in artifact_groups:
                    artifact_groups[artifact.name] = []
                artifact_groups[artifact.name].append((artifact_id, artifact))

            # For each group, keep only the latest versions
            for _name, artifacts in artifact_groups.items():
                # Sort by creation time (newest first)
                artifacts.sort(key=lambda x: x[1].created_at, reverse=True)

                # Delete older versions
                for artifact_id, _artifact in artifacts[policy.max_versions :]:
                    if policy.archive_before_delete:
                        result["archived"] += 1

                    if policy.delete_expired:
                        await self.delete_artifact(artifact_id)
                        result["deleted"] += 1

        return result

    async def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file"""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def get_artifact_metadata(self, artifact_id: str) -> ArtifactMetadata | None:
        """Get artifact metadata"""
        return self.artifacts.get(artifact_id)

    def list_artifacts(
        self,
        environment: str | None = None,
        artifact_type: ArtifactType | None = None,
        tags: builtins.dict[str, str] | None = None,
        limit: int = 100,
    ) -> builtins.list[ArtifactMetadata]:
        """List artifacts with filtering"""

        filtered_artifacts = []

        for artifact in self.artifacts.values():
            # Apply filters
            if environment and artifact.environment != environment:
                continue

            if artifact_type and artifact.artifact_type != artifact_type:
                continue

            if tags:
                if not all(artifact.tags.get(key) == value for key, value in tags.items()):
                    continue

            filtered_artifacts.append(artifact)

            if len(filtered_artifacts) >= limit:
                break

        # Sort by creation time (newest first)
        filtered_artifacts.sort(key=lambda a: a.created_at, reverse=True)

        return filtered_artifacts

    def get_promotion_status(self, request_id: str) -> PromotionRequest | None:
        """Get promotion request status"""
        return self.promotion_requests.get(request_id)

    def list_promotion_requests(
        self,
        artifact_id: str | None = None,
        status: PromotionStatus | None = None,
        limit: int = 50,
    ) -> builtins.list[PromotionRequest]:
        """List promotion requests with filtering"""

        requests = list(self.promotion_requests.values())

        # Apply filters
        if artifact_id:
            requests = [r for r in requests if r.artifact_id == artifact_id]

        if status:
            requests = [r for r in requests if r.status == status]

        # Sort by request time (newest first)
        requests.sort(key=lambda r: r.requested_at, reverse=True)

        return requests[:limit]

    def get_artifact_metrics(self) -> builtins.dict[str, Any]:
        """Get artifact management metrics"""

        total_artifacts = len(self.artifacts)
        environments = {}
        types = {}
        total_size = 0

        for artifact in self.artifacts.values():
            # Count by environment
            environments[artifact.environment] = environments.get(artifact.environment, 0) + 1

            # Count by type
            type_name = artifact.artifact_type.value
            types[type_name] = types.get(type_name, 0) + 1

            # Sum size
            total_size += artifact.file_size

        # Promotion metrics
        total_promotions = len(self.promotion_requests)
        promotion_status_counts = {}

        for request in self.promotion_requests.values():
            status = request.status.value
            promotion_status_counts[status] = promotion_status_counts.get(status, 0) + 1

        return {
            "total_artifacts": total_artifacts,
            "total_size_mb": total_size / (1024 * 1024),
            "by_environment": environments,
            "by_type": types,
            "total_promotions": total_promotions,
            "promotion_status": promotion_status_counts,
            "storage_backends": list(self.storage_backends.keys()),
            "retention_policies": len(self.retention_policies),
        }


# Example usage and demo
async def demo_artifact_management():
    """Demonstration of artifact management system"""

    print("=== Artifact Management Demo ===")

    # Initialize artifact manager with local storage
    storage_config = StorageConfiguration(
        backend=StorageBackend.LOCAL,
        base_path="./demo_artifacts",
        compression_enabled=True,
    )

    artifact_manager = ArtifactManager(storage_config)

    # Create sample artifacts
    print("\n📦 Creating Sample Artifacts")

    # Create test files
    test_files = []
    for i in range(3):
        test_file = f"test_artifact_{i}.txt"
        with open(test_file, "w") as f:
            f.write(f"Sample artifact content {i}\n" * 100)
        test_files.append(test_file)

    # Store artifacts
    artifact_ids = []

    try:
        for i, test_file in enumerate(test_files):
            artifact_id = await artifact_manager.store_artifact(
                pipeline_execution_id=f"exec_{i}",
                name="test_app",
                version=f"1.{i}.0",
                artifact_type=ArtifactType.BINARY if i == 0 else ArtifactType.CONTAINER_IMAGE,
                file_path=test_file,
                environment="development",
                tags={"component": "api", "team": "platform"},
                labels={"critical": "true" if i == 0 else "false"},
            )
            artifact_ids.append(artifact_id)
            print(f"Stored: {artifact_id}")

        # Add retention policy
        retention_policy = RetentionPolicy(
            name="dev_cleanup",
            description="Clean up old development artifacts",
            max_age_days=30,
            max_versions=5,
            environments=["development"],
            delete_expired=True,
            archive_before_delete=True,
        )

        artifact_manager.add_retention_policy(retention_policy)

        # Promote artifact
        print("\n🚀 Testing Artifact Promotion")

        promotion_request_id = await artifact_manager.promote_artifact(
            artifact_id=artifact_ids[0],
            target_environment="staging",
            requested_by="ci_system",
            reason="Automated promotion after successful tests",
            approval_required=False,
        )

        print(f"Promotion completed: {promotion_request_id}")

        # Test artifact retrieval
        print("\n📥 Testing Artifact Retrieval")

        retrieval_path = "retrieved_artifact.txt"
        success = await artifact_manager.retrieve_artifact(artifact_ids[0], retrieval_path)

        if success:
            print(f"Successfully retrieved artifact to: {retrieval_path}")
            with open(retrieval_path) as f:
                content = f.read()[:100]
                print(f"Content preview: {content}...")

        # List artifacts
        print("\n📋 Artifact Listing")

        dev_artifacts = artifact_manager.list_artifacts(environment="development", limit=10)

        print(f"Development artifacts: {len(dev_artifacts)}")
        for artifact in dev_artifacts:
            print(f"  - {artifact.name} v{artifact.version} ({artifact.artifact_type.value})")

        # Show metrics
        print("\n📊 Artifact Metrics")

        metrics = artifact_manager.get_artifact_metrics()
        print(f"Total artifacts: {metrics['total_artifacts']}")
        print(f"Total size: {metrics['total_size_mb']:.1f} MB")
        print(f"By environment: {metrics['by_environment']}")
        print(f"By type: {metrics['by_type']}")

        # Apply retention policies
        print("\n🧹 Applying Retention Policies")

        retention_result = await artifact_manager.apply_retention_policies()
        print(f"Policies applied: {retention_result['policies_applied']}")
        print(f"Artifacts processed: {retention_result['artifacts_processed']}")

    finally:
        # Clean up test files
        for test_file in test_files:
            if os.path.exists(test_file):
                os.unlink(test_file)

        if os.path.exists("retrieved_artifact.txt"):
            os.unlink("retrieved_artifact.txt")

        # Clean up demo artifacts directory
        if os.path.exists("./demo_artifacts"):
            shutil.rmtree("./demo_artifacts")


if __name__ == "__main__":
    asyncio.run(demo_artifact_management())
