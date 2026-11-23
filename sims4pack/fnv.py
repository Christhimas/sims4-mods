"""Hashes FNV-1 usados pelo The Sims 4 (instâncias de tuning e chaves de string)."""

from __future__ import annotations

_FNV32_OFFSET = 0x811C9DC5
_FNV32_PRIME = 0x01000193
_FNV64_OFFSET = 0xCBF29CE484222325
_FNV64_PRIME = 0x100000001B3

HIGH_BIT_64 = 0x8000000000000000


def fnv32(text: str) -> int:
    h = _FNV32_OFFSET
    for b in text.lower().encode("utf-8"):
        h = (h * _FNV32_PRIME) & 0xFFFFFFFF
        h ^= b
    return h


def fnv64(text: str) -> int:
    h = _FNV64_OFFSET
    for b in text.lower().encode("utf-8"):
        h = (h * _FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
        h ^= b
    return h


def tuning_instance_id(name: str) -> int:
    """ID de instância para tuning custom: FNV64 do nome com o bit alto ligado.

    O bit alto (mesma convenção do Sims 4 Studio) evita colisão com IDs da EA.
    """
    return fnv64(name) | HIGH_BIT_64


def string_key(namespaced_key: str) -> int:
    """Chave de STBL (32 bits) a partir de uma chave textual 'mod:chave'."""
    return fnv32(namespaced_key)
