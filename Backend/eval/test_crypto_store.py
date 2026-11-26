"""Tests for crypto_store.py. No Mongo needed: FakeKeys stands in for user_keys."""
import asyncio
import base64
import os
import sys

# A throwaway key for tests only, so the real one in .env is never touched.
os.environ["REACHER_MASTER_KEY"] = base64.b64encode(os.urandom(32)).decode()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cryptography.exceptions import InvalidTag
import crypto_store as cs

cs._master.cache_clear()


class FakeKeys:
    def __init__(self):
        self.docs = {}

    async def find_one(self, q):
        return self.docs.get(q["user_id"])

    async def insert_one(self, doc):
        self.docs[doc["user_id"]] = doc


def run(coro):
    return asyncio.run(coro)


def test_round_trip():
    k = FakeKeys()
    blob = run(cs.encrypt_field(k, "a@x.com", "memory", "exclude Meta"))
    assert b"exclude Meta" not in blob
    assert run(cs.decrypt_field(k, "a@x.com", "memory", blob)) == "exclude Meta"


def test_same_text_differs():
    k = FakeKeys()
    a = run(cs.encrypt_field(k, "a@x.com", "memory", "hi"))
    b = run(cs.encrypt_field(k, "a@x.com", "memory", "hi"))
    assert a != b  # new nonce each time


def test_tamper_fails():
    k = FakeKeys()
    blob = bytearray(run(cs.encrypt_field(k, "a@x.com", "memory", "hi")))
    blob[-1] ^= 1
    try:
        run(cs.decrypt_field(k, "a@x.com", "memory", bytes(blob)))
        assert False, "tampered blob decrypted"
    except InvalidTag:
        pass


def test_wrong_user_or_field_fails():
    k = FakeKeys()
    blob = run(cs.encrypt_field(k, "a@x.com", "memory", "hi"))
    run(cs.encrypt_field(k, "b@x.com", "memory", "x"))  # b gets its own key
    for uid, field in [("b@x.com", "memory"), ("a@x.com", "resume_text")]:
        try:
            run(cs.decrypt_field(k, uid, field, blob))
            assert False, f"blob opened as {uid}/{field}"
        except InvalidTag:
            pass


def test_shredded_key_fails():
    k = FakeKeys()
    blob = run(cs.encrypt_field(k, "a@x.com", "memory", "hi"))
    k.docs.clear()  # "Clear my data"
    try:
        run(cs.decrypt_field(k, "a@x.com", "memory", blob))
        assert False, "shredded data decrypted"
    except KeyError:
        pass
    assert k.docs == {}  # decrypt never makes a new key


def test_missing_master_key_fails():
    saved = os.environ.pop("REACHER_MASTER_KEY")
    cs._master.cache_clear()
    try:
        run(cs.encrypt_field(FakeKeys(), "a@x.com", "memory", "hi"))
        assert False, "worked without a master key"
    except RuntimeError:
        pass
    finally:
        os.environ["REACHER_MASTER_KEY"] = saved
        cs._master.cache_clear()
