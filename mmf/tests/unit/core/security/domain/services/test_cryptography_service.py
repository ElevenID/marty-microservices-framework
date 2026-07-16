from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mmf.core.security.domain.services.cryptography_service import CryptographyService


class TestCryptographyService:
    @pytest.fixture
    def crypto_service(self):
        return CryptographyService("test-service")

    def test_initialization(self, crypto_service):
        assert crypto_service.service_name == "test-service"
        assert crypto_service.master_key is not None
        assert isinstance(crypto_service.encryption_keys, dict)
        assert isinstance(crypto_service.signing_keys, dict)

    def test_encrypt_decrypt_data(self, crypto_service):
        data = "secret message"
        key_id = "test-key"

        encrypted = crypto_service.encrypt_data(data, key_id)
        assert encrypted != data

        decrypted = crypto_service.decrypt_data(encrypted, key_id)
        assert decrypted == data

    def test_encrypt_decrypt_bytes(self, crypto_service):
        data = b"secret bytes"
        key_id = "test-key-bytes"

        encrypted = crypto_service.encrypt_data(data, key_id)
        decrypted = crypto_service.decrypt_data(encrypted, key_id)

        assert decrypted == data.decode("utf-8")

    def test_decrypt_invalid_key(self, crypto_service):
        data = "secret"
        key_id = "key1"
        encrypted = crypto_service.encrypt_data(data, key_id)

        with pytest.raises(ValueError, match="Encryption key key2 not found"):
            crypto_service.decrypt_data(encrypted, "key2")

    def test_decrypt_corrupted_data(self, crypto_service):
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto_service.decrypt_data("invalid-base64", "default")

    def test_sign_verify_data(self, crypto_service):
        data = "important document"
        key_id = "signing-key"

        signature = crypto_service.sign_data(data, key_id)
        assert signature is not None

        is_valid = crypto_service.verify_signature(data, signature, key_id)
        assert is_valid is True

    def test_verify_invalid_signature(self, crypto_service):
        data = "important document"
        key_id = "signing-key"

        signature = crypto_service.sign_data(data, key_id)

        is_valid = crypto_service.verify_signature("tampered document", signature, key_id)
        assert is_valid is False

    def test_verify_missing_key(self, crypto_service):
        is_valid = crypto_service.verify_signature("data", "signature", "missing-key")
        assert is_valid is False

    def test_hash_verify_password(self, crypto_service):
        password = "secure-password"  # pragma: allowlist secret
        hashed = crypto_service.hash_password(password)

        assert hashed != password
        assert crypto_service.verify_password(password, hashed) is True
        assert crypto_service.verify_password("wrong-password", hashed) is False

    def test_verify_password_invalid_hash(self, crypto_service):
        assert crypto_service.verify_password("password", "invalid-hash") is False

    def test_generate_secure_token(self, crypto_service):
        token1 = crypto_service.generate_secure_token()
        token2 = crypto_service.generate_secure_token()

        assert len(token1) > 0
        assert token1 != token2

    def test_rotate_key(self, crypto_service):
        key_id = "rotation-key"
        data = "data"

        # Initial encryption
        _encrypted1 = crypto_service.encrypt_data(data, key_id)
        key1 = crypto_service.encryption_keys[key_id]
        version1 = crypto_service.key_versions[key_id]

        # Rotate
        crypto_service.rotate_key(key_id)

        key2 = crypto_service.encryption_keys[key_id]
        version2 = crypto_service.key_versions[key_id]

        assert key1 != key2
        assert version2 > version1

        # Verify schedule
        assert key_id in crypto_service.key_rotation_schedule
        assert crypto_service.key_rotation_schedule[key_id] > datetime.now(timezone.utc)

    def test_should_rotate_key(self, crypto_service):
        key_id = "check-rotation"

        # New key (not in schedule) should rotate
        assert crypto_service.should_rotate_key(key_id) is True

        # Rotate
        crypto_service.rotate_key(key_id)
        assert crypto_service.should_rotate_key(key_id) is False

        # Mock time to force rotation
        future_time = datetime.now(timezone.utc) + timedelta(days=91)
        with patch(
            "mmf.core.security.domain.services.cryptography_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = future_time
            mock_datetime.side_effect = datetime
            assert crypto_service.should_rotate_key(key_id) is True
