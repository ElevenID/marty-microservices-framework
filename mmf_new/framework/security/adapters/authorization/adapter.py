"""
Authorization Adapter

Adapter for Core Authorization Service.
"""

from __future__ import annotations

import logging

from mmf_new.core.security.domain.models.context import AuthorizationContext
from mmf_new.core.security.domain.models.result import AuthorizationResult
from mmf_new.core.security.domain.models.user import User
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.framework.authorization.api import IAuthorizer as CoreIAuthorizer

logger = logging.getLogger(__name__)


class CoreAuthorizerAdapter(IAuthorizer):
    """Adapter for Core Authorization Service."""

    def __init__(self, authorizer: CoreIAuthorizer):
        self.authorizer = authorizer

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize using Core Authorization Service."""
        try:
            result = self.authorizer.authorize(context)

            return AuthorizationResult(
                allowed=result.allowed,
                reason=result.reason,
                policies_evaluated=result.policies_evaluated,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.error(f"Authorization failed: {e}")
            return AuthorizationResult(allowed=False, reason=str(e))

    def get_user_permissions(self, user: User) -> set[str]:
        """Get permissions using Core Authorization Service."""
        try:
            permissions = self.authorizer.get_user_permissions(user)
            return set(permissions)
        except Exception as e:
            logger.error(f"Get permissions failed: {e}")
            return set()
