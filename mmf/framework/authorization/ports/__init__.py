"""
Authorization Ports - Protocol-based interfaces.

This module exports all authorization port interfaces following
hexagonal architecture principles.
"""

from .abac import (
    ABACContext,
    IABACPolicy,
    IConditionEvaluator,
    IPolicyCache,
    IPolicyEvaluator,
    IPolicyMatcher,
    IPolicyRepository,
    PolicyEvaluationResult,
)

__all__ = [
    "IConditionEvaluator",
    "IPolicyMatcher",
    "IABACPolicy",
    "IPolicyRepository",
    "IPolicyEvaluator",
    "IPolicyCache",
    "PolicyEvaluationResult",
    "ABACContext",
]
