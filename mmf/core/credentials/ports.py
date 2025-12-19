"""
Credential Ports

This module defines the interfaces for OID4VC credential operations following hexagonal architecture.
These ports define the boundary between the application core and external adapters (like SpruceID).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class CredentialFormat(Enum):
    """Supported credential formats."""

    JWT_VC = "jwt_vc_json"
    JWT_VC_JSON_LD = "jwt_vc_json-ld"
    LDP_VC = "ldp_vc"
    SD_JWT_VC = "vc+sd-jwt"
    MDOC = "mso_mdoc"


class KeyAlgorithm(Enum):
    """Supported key algorithms."""

    ES256 = "ES256"  # P-256
    ES256K = "ES256K"  # secp256k1
    EDDSA = "EdDSA"  # Ed25519


@dataclass
class KeyPair:
    """Represents a cryptographic key pair."""

    did: str
    """Decentralized identifier derived from the key."""

    jwk_json: str
    """JWK representation of the key pair (includes private key)."""

    algorithm: KeyAlgorithm
    """Signing algorithm for this key."""

    created_at: datetime = field(default_factory=datetime.utcnow)
    """When the key was created."""


@dataclass
class CredentialSubject:
    """Credential subject with claims."""

    id: str | None = None
    """Subject identifier (usually a DID)."""

    claims: dict[str, Any] = field(default_factory=dict)
    """Claims about the subject."""


@dataclass
class CredentialData:
    """Verifiable Credential data."""

    id: str
    """Unique credential identifier (urn:uuid:...)."""

    types: list[str]
    """Credential types (always includes VerifiableCredential)."""

    issuer: str
    """Issuer DID."""

    subject: CredentialSubject
    """Credential subject and claims."""

    issuance_date: datetime
    """When the credential was issued."""

    expiration_date: datetime | None = None
    """When the credential expires (optional)."""

    jwt: str | None = None
    """Signed JWT representation."""


@dataclass
class CredentialOffer:
    """OID4VCI credential offer."""

    credential_issuer: str
    """URL of the credential issuer."""

    credential_types: list[str]
    """Types of credentials offered."""

    offer_id: str
    """Unique offer identifier."""

    pre_authorized_code: str | None = None
    """Pre-authorized code for direct issuance."""

    user_pin_required: bool = False
    """Whether a user PIN is required."""

    offer_uri: str | None = None
    """Full offer URI for QR code."""

    offer_json: str | None = None
    """Full offer JSON."""


@dataclass
class PresentationRequest:
    """Presentation request from a verifier."""

    request_id: str
    """Unique request identifier."""

    verifier: str
    """Verifier identifier."""

    requested_credentials: list[str]
    """Types of credentials requested."""

    nonce: str
    """Cryptographic nonce."""

    audience: str
    """Expected audience for the presentation."""


@dataclass
class VerificationResult:
    """Result of credential or presentation verification."""

    valid: bool
    """Whether verification succeeded."""

    claims: dict[str, Any] = field(default_factory=dict)
    """Extracted claims from the verified credential."""

    error: str | None = None
    """Error message if verification failed."""

    issuer: str | None = None
    """Verified issuer if available."""


@runtime_checkable
class IKeyManager(Protocol):
    """Interface for cryptographic key management."""

    def generate_key(self, algorithm: KeyAlgorithm = KeyAlgorithm.ES256) -> KeyPair:
        """
        Generate a new key pair.

        Args:
            algorithm: Key algorithm to use (default: ES256 for P-256 curve)

        Returns:
            Generated key pair with DID and JWK
        """
        ...

    def store_key(self, key_id: str, key_pair: KeyPair) -> None:
        """
        Store a key pair securely.

        Args:
            key_id: Identifier for the key
            key_pair: Key pair to store
        """
        ...

    def get_key(self, key_id: str) -> KeyPair | None:
        """
        Retrieve a stored key pair.

        Args:
            key_id: Identifier for the key

        Returns:
            The key pair if found, None otherwise
        """
        ...

    def list_keys(self) -> list[str]:
        """
        List all stored key identifiers.

        Returns:
            List of key identifiers
        """
        ...


@runtime_checkable
class ICredentialIssuer(Protocol):
    """Interface for credential issuance (issuer role in OID4VCI)."""

    def create_credential(
        self,
        issuer_key: KeyPair,
        credential_type: str,
        subject: CredentialSubject,
        expiration_seconds: int | None = None,
    ) -> CredentialData:
        """
        Create and sign a verifiable credential.

        Args:
            issuer_key: Key pair for signing
            credential_type: Type of credential (e.g., "UniversityDegreeCredential")
            subject: Subject and claims for the credential
            expiration_seconds: Credential validity period in seconds (optional)

        Returns:
            Created credential with signed JWT
        """
        ...

    def create_offer(
        self,
        issuer_url: str,
        credential_types: list[str],
        pre_authorized: bool = True,
        user_pin_required: bool = False,
        wallet_format: str = "standard",
    ) -> CredentialOffer:
        """
        Create an OID4VCI credential offer.

        Args:
            issuer_url: Base URL of the issuer
            credential_types: Types of credentials to offer
            pre_authorized: Use pre-authorized code flow
            user_pin_required: Require user PIN for redemption
            wallet_format: Target wallet format ("standard" or "microsoft")

        Returns:
            Credential offer with URI for QR code display
        """
        ...

    def generate_issuer_metadata(
        self,
        issuer_url: str,
        issuer_name: str,
        supported_credentials: list[dict[str, Any]],
    ) -> str:
        """
        Generate OID4VCI issuer metadata for discovery.

        Args:
            issuer_url: Base URL of the issuer
            issuer_name: Display name of the issuer
            supported_credentials: List of supported credential configurations

        Returns:
            JSON string of issuer metadata
        """
        ...


@runtime_checkable
class ICredentialWallet(Protocol):
    """Interface for credential wallet operations (holder role in OID4VCI)."""

    def store_credential(self, credential: CredentialData) -> str:
        """
        Store a credential in the wallet.

        Args:
            credential: Credential to store

        Returns:
            Storage identifier for the credential
        """
        ...

    def get_credential(self, credential_id: str) -> CredentialData | None:
        """
        Retrieve a stored credential.

        Args:
            credential_id: Identifier of the credential

        Returns:
            The credential if found, None otherwise
        """
        ...

    def list_credentials(self, credential_type: str | None = None) -> list[CredentialData]:
        """
        List stored credentials.

        Args:
            credential_type: Filter by type (optional)

        Returns:
            List of matching credentials
        """
        ...

    def create_presentation(
        self,
        holder_key: KeyPair,
        credentials: list[CredentialData],
        audience: str,
        nonce: str | None = None,
    ) -> str:
        """
        Create a verifiable presentation.

        Args:
            holder_key: Holder's key for signing
            credentials: Credentials to include
            audience: Verifier identifier
            nonce: Cryptographic nonce (optional)

        Returns:
            Signed presentation JWT
        """
        ...

    def redeem_offer(self, offer_uri: str, holder_key: KeyPair) -> CredentialData:
        """
        Redeem a credential offer from an issuer.

        Args:
            offer_uri: URI from the credential offer
            holder_key: Holder's key for binding

        Returns:
            Received credential
        """
        ...


@runtime_checkable
class ICredentialVerifier(Protocol):
    """Interface for credential verification (verifier role in OID4VCI/OID4VP)."""

    def verify_credential(
        self,
        credential_jwt: str,
        expected_issuer: str | None = None,
    ) -> VerificationResult:
        """
        Verify a credential JWT.

        Args:
            credential_jwt: Credential JWT to verify
            expected_issuer: Expected issuer DID (optional)

        Returns:
            Verification result with claims if valid
        """
        ...

    def verify_presentation(
        self,
        presentation_jwt: str,
        expected_audience: str,
        expected_nonce: str | None = None,
    ) -> VerificationResult:
        """
        Verify a presentation JWT.

        Args:
            presentation_jwt: Presentation JWT to verify
            expected_audience: Expected audience (verifier)
            expected_nonce: Expected nonce if provided in request

        Returns:
            Verification result with claims if valid
        """
        ...

    def create_presentation_request(
        self,
        verifier_id: str,
        requested_credentials: list[str],
    ) -> PresentationRequest:
        """
        Create a presentation request for OID4VP.

        Args:
            verifier_id: Identifier for the verifier
            requested_credentials: Types of credentials requested

        Returns:
            Presentation request with nonce
        """
        ...
