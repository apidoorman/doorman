import os
import pytest

from utils.token_util import encrypt_value, decrypt_value, get_token_api_header
from services.token_service import TokenService
from models.token_model import TokenModel
from models.user_tokens_model import UserTokenModel
from utils.database import token_def_collection, user_token_collection


@pytest.fixture(autouse=True)
def _set_enc_key(monkeypatch):
    # Provide a stable encryption key for tests
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-encryption-key-123")


def test_encrypt_decrypt_roundtrip():
    secret = "s3cr3t"
    enc = encrypt_value(secret)
    assert enc and enc.startswith("enc:")
    dec = decrypt_value(enc)
    assert dec == secret


@pytest.mark.asyncio
async def test_token_definition_stored_encrypted_and_read_decrypted():
    data = TokenModel(
        api_token_group="grp1",
        api_key="ABC123",
        api_key_header="X-API-Key",
        token_tiers=[{"tier_name": "basic", "tokens": 10, "input_limit": 100, "output_limit": 100, "reset_frequency": "monthly"}],
    )
    res = await TokenService.create_token(data, request_id="r1")
    assert res["status_code"] in (201, 400)  # created or exists if rerun
    doc = token_def_collection.find_one({"api_token_group": "grp1"})
    assert doc is not None
    # At rest must be encrypted (or already encrypted)
    assert isinstance(doc.get("api_key"), str)
    assert doc["api_key"].startswith("enc:")
    # Retrieval uses decrypt path
    header, key = await __get_header("grp1")
    assert header == "X-API-Key"
    assert key == "ABC123"


async def __get_header(group: str):
    from utils.token_util import get_token_api_header
    return await get_token_api_header(group)


@pytest.mark.asyncio
async def test_user_tokens_stored_encrypted_and_return_decrypted():
    username = "admin"
    payload = UserTokenModel(
        username=username,
        users_tokens={
            "grp1": {"tier_name": "basic", "user_api_key": "U-KEY-1", "available_tokens": 2}
        },
    )
    res = await TokenService.add_tokens(username, payload, request_id="r2")
    assert res["status_code"] in (200, 201)
    # At rest is encrypted
    doc = user_token_collection.find_one({"username": username})
    assert doc is not None
    val = doc["users_tokens"]["grp1"]["user_api_key"]
    assert isinstance(val, str) and val.startswith("enc:")
    # Reading API returns decrypted value
    res2 = await TokenService.get_user_tokens(username, request_id="r3")
    assert res2["status_code"] == 200
    ut = res2["response"]["users_tokens"]
    assert ut["grp1"]["user_api_key"] == "U-KEY-1"
