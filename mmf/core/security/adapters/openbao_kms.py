"""OpenBao Transit KMS Provider for MMF.

Implements ``IKMSProvider`` using OpenBao's (or HashiCorp Vault's) Transit
secrets engine for signing, encryption, and key management.  All private key
material stays inside the Transit engine — application code never sees it.

OpenBao is an Apache-2.0 fork of HashiCorp Vault and shares the same REST API,
so this adapter works with both OpenBao and Vault.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from mmf.core.security.ports.kms import (
    IKMSProvider,
    KeyAlgorithm,
    KeyMaterial,
    KeyMetadata,
    KeyOperation,
    KMSProviderType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Algorithm mapping: MMF KeyAlgorithm ↔ OpenBao Transit key type
# ---------------------------------------------------------------------------

_ALGO_TO_TRANSIT_TYPE: dict[KeyAlgorithm, str] = {
    KeyAlgorithm.ES256: "ecdsa-p256",
    KeyAlgorithm.ES384: "ecdsa-p384",
    KeyAlgorithm.ES512: "ecdsa-p521",
    KeyAlgorithm.EDDSA: "ed25519",
    KeyAlgorithm.RS256: "rsa-2048",
    KeyAlgorithm.RS384: "rsa-3072",
    KeyAlgorithm.RS512: "rsa-4096",
    KeyAlgorithm.PS256: "rsa-2048",
    KeyAlgorithm.PS384: "rsa-3072",
    KeyAlgorithm.PS512: "rsa-4096",
    KeyAlgorithm.AES_128: "aes128-gcm96",
    KeyAlgorithm.AES_256: "aes256-gcm96",
}

_ALGO_TO_HASH: dict[KeyAlgorithm, str] = {
    KeyAlgorithm.ES256: "sha2-256",
    KeyAlgorithm.ES384: "sha2-384",
    KeyAlgorithm.ES512: "sha2-512",
    KeyAlgorithm.EDDSA: "none",
    KeyAlgorithm.RS256: "sha2-256",
    KeyAlgorithm.RS384: "sha2-384",
    KeyAlgorithm.RS512: "sha2-512",
    KeyAlgorithm.PS256: "sha2-256",
    KeyAlgorithm.PS384: "sha2-384",
    KeyAlgorithm.PS512: "sha2-512",
}

_PSS_ALGORITHMS = {KeyAlgorithm.PS256, KeyAlgorithm.PS384, KeyAlgorithm.PS512}


def _safe_key_name(key_id: str) -> str:
    """Convert a key ID to a Transit-safe key name (no colons)."""
    return key_id.replace(":", "-")


class OpenBaoKMSProvider:
    """MMF ``IKMSProvider`` backed by OpenBao/Vault Transit secrets engine.

    Parameters
    ----------
    addr:
        Base URL for the OpenBao/Vault server (e.g. ``http://openbao:8200``).
    token:
        API token for authentication (`X-Vault-Token`).
    transit_mount:
        Mount point of the Transit engine (default ``transit``).
    namespace:
        Optional Vault namespace for enterprise deployments.
    """

    def __init__(
        self,
        addr: str,
        token: str,
        *,
        transit_mount: str = "transit",
        namespace: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._addr = addr.rstrip("/")
        self._transit_mount = transit_mount
        headers: dict[str, str] = {"X-Vault-Token": token}
        if namespace:
            headers["X-Vault-Namespace"] = namespace
        self._client = httpx.AsyncClient(
            base_url=self._addr,
            headers=headers,
            timeout=timeout,
        )

    # -- helpers ---------------------------------------------------------------

    def _transit_url(self, action: str, key_name: str) -> str:
        return f"/v1/{self._transit_mount}/{action}/{key_name}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        resp = await self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    # -- IKMSProvider ----------------------------------------------------------

    @property
    def provider_type(self) -> KMSProviderType:
        return KMSProviderType.HASHICORP_VAULT

    async def generate_key(
        self,
        key_id: str,
        algorithm: KeyAlgorithm,
        *,
        expires_at: datetime | None = None,
        require_hardware: bool = False,
        labels: dict[str, str] | None = None,
    ) -> KeyMaterial:
        key_name = _safe_key_name(key_id)
        transit_type = _ALGO_TO_TRANSIT_TYPE.get(algorithm, "ecdsa-p256")

        await self._request(
            "POST",
            self._transit_url("keys", key_name),
            json={"type": transit_type, "exportable": False},
        )

        # Fetch public key
        data = await self._request("GET", self._transit_url("keys", key_name))
        keys_data = data.get("data", {}).get("keys", {})
        latest_version = str(data.get("data", {}).get("latest_version", 1))
        public_key_pem = keys_data.get(latest_version, {}).get("public_key", "").encode()

        now = datetime.now(timezone.utc)
        metadata = KeyMetadata(
            key_id=key_id,
            algorithm=algorithm,
            provider_type=KMSProviderType.HASHICORP_VAULT,
            provider_key_id=key_name,
            created_at=now,
            expires_at=expires_at,
            is_hardware_backed=False,
            allowed_operations=[
                KeyOperation.SIGN,
                KeyOperation.VERIFY,
                KeyOperation.EXPORT_PUBLIC,
            ],
            labels=labels or {},
        )

        logger.info("Generated Transit key %s (type=%s)", key_name, transit_type)
        return KeyMaterial(metadata=metadata, public_key_pem=public_key_pem)

    async def sign(
        self,
        key_id: str,
        data: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
    ) -> bytes:
        key_name = _safe_key_name(key_id)
        input_b64 = base64.b64encode(data).decode()

        payload: dict[str, Any] = {"input": input_b64}
        if algorithm:
            hash_alg = _ALGO_TO_HASH.get(algorithm)
            if hash_alg and hash_alg != "none":
                payload["hash_algorithm"] = hash_alg
            if algorithm in _PSS_ALGORITHMS:
                payload["signature_algorithm"] = "pss"
            payload["prehashed"] = False

        result = await self._request(
            "POST",
            self._transit_url("sign", key_name),
            json=payload,
        )

        # Transit returns "vault:v1:<base64sig>"
        sig_str: str = result["data"]["signature"]
        raw_b64 = sig_str.rsplit(":", 1)[-1]
        return base64.b64decode(raw_b64)

    async def verify(
        self,
        key_id: str,
        data: bytes,
        signature: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
    ) -> bool:
        key_name = _safe_key_name(key_id)
        input_b64 = base64.b64encode(data).decode()
        sig_b64 = base64.b64encode(signature).decode()
        sig_prefixed = f"vault:v1:{sig_b64}"

        payload: dict[str, Any] = {"input": input_b64, "signature": sig_prefixed}
        if algorithm:
            hash_alg = _ALGO_TO_HASH.get(algorithm)
            if hash_alg and hash_alg != "none":
                payload["hash_algorithm"] = hash_alg

        result = await self._request(
            "POST",
            self._transit_url("verify", key_name),
            json=payload,
        )
        return result.get("data", {}).get("valid", False)

    async def encrypt(
        self,
        key_id: str,
        plaintext: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
        additional_data: bytes | None = None,
    ) -> bytes:
        key_name = _safe_key_name(key_id)
        input_b64 = base64.b64encode(plaintext).decode()

        payload: dict[str, Any] = {"plaintext": input_b64}
        if additional_data:
            payload["context"] = base64.b64encode(additional_data).decode()

        result = await self._request(
            "POST",
            self._transit_url("encrypt", key_name),
            json=payload,
        )
        ciphertext_str: str = result["data"]["ciphertext"]
        return ciphertext_str.encode()

    async def decrypt(
        self,
        key_id: str,
        ciphertext: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
        additional_data: bytes | None = None,
    ) -> bytes:
        key_name = _safe_key_name(key_id)

        payload: dict[str, Any] = {"ciphertext": ciphertext.decode()}
        if additional_data:
            payload["context"] = base64.b64encode(additional_data).decode()

        result = await self._request(
            "POST",
            self._transit_url("decrypt", key_name),
            json=payload,
        )
        plaintext_b64: str = result["data"]["plaintext"]
        return base64.b64decode(plaintext_b64)

    async def get_public_key(self, key_id: str) -> bytes:
        key_name = _safe_key_name(key_id)
        data = await self._request("GET", self._transit_url("keys", key_name))
        keys_data = data.get("data", {}).get("keys", {})
        latest = str(data.get("data", {}).get("latest_version", 1))
        pem = keys_data.get(latest, {}).get("public_key", "")
        return pem.encode()

    async def get_public_key_jwk(self, key_id: str) -> dict[str, Any]:
        pem_bytes = await self.get_public_key(key_id)
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

        pub = load_pem_public_key(pem_bytes)
        if isinstance(pub, ec.EllipticCurvePublicKey):
            nums = pub.public_numbers()
            size = pub.key_size // 8
            from marty_backend_common.utils.base64_utils import b64url_encode

            return {
                "kty": "EC",
                "crv": {256: "P-256", 384: "P-384", 521: "P-521"}.get(pub.key_size, "P-256"),
                "x": b64url_encode(nums.x.to_bytes(size, "big")),
                "y": b64url_encode(nums.y.to_bytes(size, "big")),
            }
        if isinstance(pub, ed25519.Ed25519PublicKey):
            raw = pub.public_bytes_raw()
            return {
                "kty": "OKP",
                "crv": "Ed25519",
                "x": base64.urlsafe_b64encode(raw).rstrip(b"=").decode(),
            }
        if isinstance(pub, rsa.RSAPublicKey):
            nums = pub.public_numbers()
            return {
                "kty": "RSA",
                "n": base64.urlsafe_b64encode(
                    nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
                )
                .rstrip(b"=")
                .decode(),
                "e": base64.urlsafe_b64encode(
                    nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
                )
                .rstrip(b"=")
                .decode(),
            }
        raise ValueError(f"Unsupported key type: {type(pub)}")

    async def get_key_metadata(self, key_id: str) -> KeyMetadata | None:
        key_name = _safe_key_name(key_id)
        try:
            data = await self._request("GET", self._transit_url("keys", key_name))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

        info = data.get("data", {})
        algo_type = info.get("type", "")
        algo_map = {v: k for k, v in _ALGO_TO_TRANSIT_TYPE.items()}
        algorithm = algo_map.get(algo_type, KeyAlgorithm.ES256)

        return KeyMetadata(
            key_id=key_id,
            algorithm=algorithm,
            provider_type=KMSProviderType.HASHICORP_VAULT,
            provider_key_id=key_name,
            created_at=datetime.now(timezone.utc),
            is_hardware_backed=False,
            allowed_operations=[KeyOperation.SIGN, KeyOperation.VERIFY],
            labels=info.get("labels", {}),
        )

    async def key_exists(self, key_id: str) -> bool:
        return (await self.get_key_metadata(key_id)) is not None

    async def delete_key(self, key_id: str) -> bool:
        key_name = _safe_key_name(key_id)
        try:
            # Must allow deletion first
            await self._request(
                "POST",
                self._transit_url("keys", f"{key_name}/config"),
                json={"deletion_allowed": True},
            )
            await self._request("DELETE", self._transit_url("keys", key_name))
            return True
        except httpx.HTTPStatusError:
            return False

    async def list_keys(
        self,
        *,
        namespace: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> list[KeyMetadata]:
        try:
            result = await self._request("LIST", f"/v1/{self._transit_mount}/keys")
        except httpx.HTTPStatusError:
            return []

        key_names: list[str] = result.get("data", {}).get("keys", [])
        out: list[KeyMetadata] = []
        for name in key_names:
            key_id = name.replace("-", ":", 2)  # reverse _safe_key_name for cred: keys
            if namespace and not key_id.startswith(f"{namespace}:"):
                continue
            meta = await self.get_key_metadata(key_id)
            if meta:
                out.append(meta)
        return out

    async def rotate_key(
        self,
        key_id: str,
        *,
        new_expires_at: datetime | None = None,
    ) -> KeyMaterial:
        key_name = _safe_key_name(key_id)
        await self._request("POST", self._transit_url("keys", f"{key_name}/rotate"))

        data = await self._request("GET", self._transit_url("keys", key_name))
        keys_data = data.get("data", {}).get("keys", {})
        latest = str(data.get("data", {}).get("latest_version", 1))
        public_key_pem = keys_data.get(latest, {}).get("public_key", "").encode()

        info = data.get("data", {})
        algo_map = {v: k for k, v in _ALGO_TO_TRANSIT_TYPE.items()}
        algorithm = algo_map.get(info.get("type", ""), KeyAlgorithm.ES256)

        metadata = KeyMetadata(
            key_id=key_id,
            algorithm=algorithm,
            provider_type=KMSProviderType.HASHICORP_VAULT,
            provider_key_id=key_name,
            created_at=datetime.now(timezone.utc),
            expires_at=new_expires_at,
            is_hardware_backed=False,
        )

        logger.info("Rotated Transit key %s to version %s", key_name, latest)
        return KeyMaterial(metadata=metadata, public_key_pem=public_key_pem)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
