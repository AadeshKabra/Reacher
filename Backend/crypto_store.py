import base64, os
from datetime import datetime, timezone
from functools import lru_cache
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pymongo.errors import DuplicateKeyError

VERSION = b"\x01"


@lru_cache(maxsize=1)
def _master() -> AESGCM:
    # Read on first use, not at import, so load_dotenv() in app.py can run first.
    raw = os.environ.get("REACHER_MASTER_KEY", "").strip()
    if not raw:
        raise RuntimeError("REACHER_MASTER_KEY is not set")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("REACHER_MASTER_KEY must be 32 bytes, base64-encoded")
    return AESGCM(key)

def _seal(aead: AESGCM, data: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(12)                      # new nonce every time, never reuse
    return VERSION + nonce + aead.encrypt(nonce, data, aad)

def _open(aead: AESGCM, blob: bytes, aad: bytes) -> bytes:
    if blob[:1] != VERSION:
        raise ValueError("unknown blob version")
    return aead.decrypt(blob[1:13], blob[13:], aad)   # raises InvalidTag if tampered

async def _data_key(user_keys, user_id: str, create: bool) -> AESGCM:
    doc = await user_keys.find_one({"user_id": user_id})
    if doc is None:
        if not create:
            raise KeyError("no data key")       # shredded, or never created
        raw = AESGCM.generate_key(bit_length=256)
        try:
            await user_keys.insert_one({
                "user_id": user_id,
                "wrapped_key": _seal(_master(), raw, user_id.encode()),
                "key_version": 1,
                "created_at": datetime.now(timezone.utc),
            })
            return AESGCM(raw)
        except DuplicateKeyError:               # two requests raced, use the winner
            doc = await user_keys.find_one({"user_id": user_id})
    return AESGCM(_open(_master(), doc["wrapped_key"], user_id.encode()))

async def encrypt_field(user_keys, user_id: str, field: str, text: str) -> bytes:
    key = await _data_key(user_keys, user_id, create=True)
    return _seal(key, text.encode(), f"{user_id}|{field}".encode())

async def decrypt_field(user_keys, user_id: str, field: str, blob: bytes) -> str:
    key = await _data_key(user_keys, user_id, create=False)
    return _open(key, blob, f"{user_id}|{field}".encode()).decode()