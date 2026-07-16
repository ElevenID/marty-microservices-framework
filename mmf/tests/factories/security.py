"""
Security Factories

Provides factory_boy factories for security domain models.
"""

import uuid
from datetime import datetime, timedelta, timezone

import factory

from mmf.core.security.domain.models.user import AuthenticatedUser


class AuthenticatedUserFactory(factory.Factory):
    """Factory for AuthenticatedUser objects."""

    class Meta:
        model = AuthenticatedUser

    user_id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    username = factory.Faker("user_name")
    email = factory.Faker("email")
    roles = factory.LazyAttribute(lambda _: {"user"})
    permissions = factory.LazyAttribute(lambda _: {"read"})
    session_id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    auth_method = "password"
    expires_at = factory.LazyAttribute(lambda _: datetime.now(timezone.utc) + timedelta(hours=24))
    metadata = factory.LazyAttribute(lambda _: {})
    created_at = factory.LazyAttribute(lambda _: datetime.now(timezone.utc))
    user_type = None
    applicant_id = None

    class Params:
        """Traits for common user types."""

        # Admin user
        admin = factory.Trait(
            roles={"admin", "user"},
            permissions={"read", "write", "delete", "admin"},
            user_type="administrator",
        )

        # Guest user (limited permissions)
        guest = factory.Trait(
            username=None,
            email=None,
            roles={"guest"},
            permissions={"read"},
            auth_method="anonymous",
        )

        # Service account
        service_account = factory.Trait(
            username=factory.LazyAttribute(lambda _: f"svc_{uuid.uuid4().hex[:8]}"),
            email=None,
            roles={"service"},
            permissions={"read", "write"},
            auth_method="api_key",
        )

        # Expired session
        expired = factory.Trait(
            expires_at=factory.LazyAttribute(
                lambda _: datetime.now(timezone.utc) - timedelta(hours=1)
            ),
        )

        # Applicant user
        applicant = factory.Trait(
            user_type="applicant",
            applicant_id=factory.LazyAttribute(lambda _: str(uuid.uuid4())),
            roles={"applicant"},
            permissions={"read", "submit"},
        )

        # Multi-factor authenticated
        mfa = factory.Trait(
            auth_method="mfa",
            metadata=factory.LazyAttribute(
                lambda _: {
                    "mfa_verified": True,
                    "mfa_method": "totp",
                }
            ),
        )

        # OAuth authenticated
        oauth = factory.Trait(
            auth_method="oauth2",
            metadata=factory.LazyAttribute(
                lambda _: {
                    "provider": "google",
                    "provider_user_id": str(uuid.uuid4()),
                }
            ),
        )

        # JWT authenticated
        jwt = factory.Trait(
            auth_method="jwt",
            metadata=factory.LazyAttribute(
                lambda _: {
                    "token_type": "access",
                    "issuer": "mmf-auth",
                }
            ),
        )
