"""
Policy Engines Module

Provides concrete implementations of policy engines for evaluating authorization decisions.

Available Engines:
- BuiltinPolicyEngine: JSON-based policy engine with wildcard matching
- ACLPolicyEngine: Access Control List engine with resource-level permissions
- OPAPolicyEngine: Open Policy Agent integration (stub)
- OsoPolicyEngine: Oso authorization library integration (stub)

Public API:
- AbstractPolicyEngine: Base class for all policy engines
- SecurityContext: Context for policy evaluation
- SecurityDecision: Result of policy evaluation
- All concrete engine classes
"""

from .acl import ACLPolicyEngine
from .base import AbstractPolicyEngine, SecurityContext, SecurityDecision
from .builtin import BuiltinPolicyEngine
from .opa import OPAPolicyEngine
from .oso import OsoPolicyEngine

__all__ = [
    # Base types
    "AbstractPolicyEngine",
    "SecurityContext",
    "SecurityDecision",
    # Concrete engines
    "BuiltinPolicyEngine",
    "ACLPolicyEngine",
    "OPAPolicyEngine",
    "OsoPolicyEngine",
]
