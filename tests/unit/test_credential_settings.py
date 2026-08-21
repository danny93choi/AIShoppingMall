from pydantic import SecretStr

from commerce_agent.application.services.credential_settings import (
    CredentialCipher,
    CredentialConfigurationError,
)


def test_credential_cipher_encrypts_and_round_trips_payload() -> None:
    cipher = CredentialCipher(SecretStr("a-strong-local-master-key-with-32-chars"))
    payload = {"api_key": "sensitive-value", "model": "market-model"}

    encrypted = cipher.encrypt(payload)

    assert "sensitive-value" not in encrypted
    assert cipher.decrypt(encrypted) == payload


def test_credential_cipher_requires_bootstrap_master_key() -> None:
    try:
        CredentialCipher(None)
    except CredentialConfigurationError as error:
        assert "SETTINGS_MASTER_KEY" in str(error)
    else:
        raise AssertionError("missing master key must be rejected")
