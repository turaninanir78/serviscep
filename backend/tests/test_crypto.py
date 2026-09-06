from app.crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip():
    original = "EAAG_fake_meta_access_token_value_1234567890"
    encrypted = encrypt_token(original)

    assert encrypted != original
    assert decrypt_token(encrypted) == original
