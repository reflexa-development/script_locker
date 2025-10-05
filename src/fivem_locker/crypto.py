from __future__ import annotations

import base64
from typing import Tuple

# Simple FNV-1a 32-bit for deterministic PRNG seeding
FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193


def fnv1a32(data: bytes, seed: int = FNV_OFFSET) -> int:
    value = seed & 0xFFFFFFFF
    for b in data:
        value ^= b
        value = (value * FNV_PRIME) & 0xFFFFFFFF
    return value


def xorshift32(x: int) -> int:
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17) & 0xFFFFFFFF
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def keystream(length: int, seed: int) -> bytes:
    out = bytearray()
    state = seed & 0xFFFFFFFF
    for _ in range(length):
        state = xorshift32(state)
        out.append(state & 0xFF)
    return bytes(out)


def encrypt_xor_stream(plaintext: bytes, key: bytes, side_tag: str) -> bytes:
    """
    Encrypts using XOR stream derived from FNV-1a(key + salt + side_tag) and xorshift32.
    Returns: salt(8) + ciphertext
    """
    import os

    salt = os.urandom(8)
    seed_material = key + salt + side_tag.encode("utf-8")
    seed = fnv1a32(seed_material)
    ks = keystream(len(plaintext), seed)
    ciphertext = bytes(p ^ k for p, k in zip(plaintext, ks))
    return salt + ciphertext


def decrypt_xor_stream(blob: bytes, key: bytes, side_tag: str) -> bytes:
    if len(blob) < 8:
        raise ValueError("blob too small; missing salt")
    salt = blob[:8]
    ciphertext = blob[8:]
    seed_material = key + salt + side_tag.encode("utf-8")
    seed = fnv1a32(seed_material)
    ks = keystream(len(ciphertext), seed)
    return bytes(c ^ k for c, k in zip(ciphertext, ks))


def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64_decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))
