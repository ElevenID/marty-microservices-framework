import pytest

from mmf.core.security.domain.enums import (
    AuthenticationMethod,
    ComplianceFramework,
    IdentityProviderType,
    PermissionAction,
    PolicyEngineType,
    SecurityPolicyType,
)


class TestSecurityEnums:
    def test_authentication_method_values(self):
        assert AuthenticationMethod.PASSWORD.value == "password"
        assert AuthenticationMethod.TOKEN.value == "token"
        assert AuthenticationMethod.CERTIFICATE.value == "certificate"
        assert AuthenticationMethod.OAUTH2.value == "oauth2"
        assert AuthenticationMethod.OIDC.value == "oidc"
        assert AuthenticationMethod.SAML.value == "saml"

    def test_permission_action_values(self):
        assert PermissionAction.READ.value == "read"
        assert PermissionAction.WRITE.value == "write"
        assert PermissionAction.DELETE.value == "delete"
        assert PermissionAction.EXECUTE.value == "execute"
        assert PermissionAction.ADMIN.value == "admin"

    def test_policy_engine_type_values(self):
        assert PolicyEngineType.BUILTIN.value == "builtin"
        assert PolicyEngineType.OPA.value == "opa"
        assert PolicyEngineType.OSO.value == "oso"
        assert PolicyEngineType.ACL.value == "acl"
        assert PolicyEngineType.CUSTOM.value == "custom"

    def test_compliance_framework_values(self):
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.SOX.value == "sox"
        assert ComplianceFramework.PCI_DSS.value == "pci_dss"
        assert ComplianceFramework.ISO27001.value == "iso27001"
        assert ComplianceFramework.NIST.value == "nist"

    def test_identity_provider_type_values(self):
        assert IdentityProviderType.OIDC.value == "oidc"
        assert IdentityProviderType.OAUTH2.value == "oauth2"
        assert IdentityProviderType.SAML.value == "saml"
        assert IdentityProviderType.LDAP.value == "ldap"
        assert IdentityProviderType.LOCAL.value == "local"

    def test_security_policy_type_values(self):
        assert SecurityPolicyType.RBAC.value == "rbac"
        assert SecurityPolicyType.ABAC.value == "abac"
        assert SecurityPolicyType.ACL.value == "acl"
        assert SecurityPolicyType.CUSTOM.value == "custom"
