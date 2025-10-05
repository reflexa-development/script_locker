from __future__ import annotations

import os
from dataclasses import dataclass


def _fnv1a32(data: bytes) -> int:
    seed = 0x811C9DC5
    for b in data:
        seed ^= b
        seed = (seed * 0x01000193) & 0xFFFFFFFF
    return seed


def _xorshift32(seed: int) -> int:
    x = seed & 0xFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17) & 0xFFFFFFFF
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def _keystream(seed: int, length: int) -> bytes:
    out = bytearray(length)
    x = seed
    for i in range(length):
        x = _xorshift32(x)
        out[i] = x & 0xFF
    return bytes(out)


@dataclass
class LockerCrypto:
    license_key: str
    salt: str

    def _derive_seed32(self, nonce: bytes) -> int:
        material = (self.license_key + "|" + self.salt).encode("utf-8") + nonce
        return _fnv1a32(material)

    def encrypt(self, data: bytes) -> bytes:
        # Simple XOR stream using xorshift32 seeded by FNV-1a over (license|salt|nonce)
        # Tag: XRF\x00 (XOR Fallback)
        nonce = os.urandom(12)
        seed = self._derive_seed32(nonce)
        ks = _keystream(seed, len(data))
        out = bytes(a ^ b for a, b in zip(data, ks))
        return b"XRF\x00" + nonce + out

    def decrypt(self, data: bytes) -> bytes:
        # Not used in packer; loader uses Lua side
        raise NotImplementedError
