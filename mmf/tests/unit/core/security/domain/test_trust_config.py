import pytest

from mmf.core.security.domain.trust_config import (
    PKDConfig,
    TrustAnchorConfig,
    TrustStoreConfig,
)


class TestTrustConfig:
    def test_pkd_config_defaults(self):
        config = PKDConfig()
        assert config.enabled is True
        assert config.update_interval_hours == 24
        assert config.timeout_seconds == 30

    def test_pkd_config_validation(self):
        with pytest.raises(ValueError, match="PKD update interval must be positive"):
            PKDConfig(update_interval_hours=0)

        with pytest.raises(ValueError, match="PKD timeout must be positive"):
            PKDConfig(timeout_seconds=0)

    def test_trust_anchor_config_defaults(self):
        config = TrustAnchorConfig()
        assert config.certificate_store_path == "/app/data/trust"
        assert config.update_interval_hours == 24

    def test_trust_anchor_config_validation(self):
        with pytest.raises(ValueError, match="Trust anchor update interval must be positive"):
            TrustAnchorConfig(update_interval_hours=0)

    def test_trust_store_config_from_dict(self):
        data = {
            "pkd": {
                "service_url": "http://pkd.example.com",
                "enabled": False,
                "update_interval_hours": 12,
            },
            "trust_anchor": {
                "certificate_store_path": "/custom/path",
                "enable_online_verification": True,
            },
        }

        config = TrustStoreConfig.from_dict(data)

        assert config.pkd.service_url == "http://pkd.example.com"
        assert config.pkd.enabled is False
        assert config.pkd.update_interval_hours == 12

        assert config.trust_anchor.certificate_store_path == "/custom/path"
        assert config.trust_anchor.enable_online_verification is True

        # Check defaults for missing fields
        assert config.pkd.max_retries == 3
        assert config.trust_anchor.validation_timeout_seconds == 30
